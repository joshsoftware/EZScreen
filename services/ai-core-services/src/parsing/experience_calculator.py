"""Deterministic experience recalculation for parsed resume data.

Pure functions — no I/O. Overrides LLM date math with strict Python calculations.
When the resume's professional summary/description explicitly states years of experience
alongside specific skills (e.g., "6+ years of experience… Node.js, React"),
those explicit years take absolute priority over role-based calculations.
"""

from __future__ import annotations

import calendar
import datetime
import re


def _parse_date(date_str, is_end_date: bool = False) -> datetime.datetime | None:
    if not date_str or str(date_str).lower() in ("present", "current", "now", "null", "none"):
        return datetime.datetime.now()
    date_str = str(date_str).strip()
    try:
        if len(date_str) == 10:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d")
        if len(date_str) == 7:
            dt = datetime.datetime.strptime(date_str, "%Y-%m")
            if is_end_date:
                _, last_day = calendar.monthrange(dt.year, dt.month)
                dt = dt.replace(day=last_day)
            return dt
        if len(date_str) == 4:
            dt = datetime.datetime.strptime(date_str, "%Y")
            if is_end_date:
                dt = dt.replace(month=12, day=31)
            return dt
    except ValueError:
        pass
    return None


def _extract_summary_skill_years(resume_text: str, all_skills: list[str]) -> dict[str, float]:
    """Extract explicit years from summary/description paragraphs and map to skills mentioned there.

    Scans the resume text for patterns like "X+ years of experience" or "X years of expertise"
    in summary-like paragraphs. Any skill explicitly named in the SAME paragraph inherits
    that exact year value.

    Returns a dict mapping skill_name_lower -> explicit_years.
    """
    if not resume_text or not all_skills:
        return {}

    explicit_map: dict[str, float] = {}

    # Split text into paragraphs (blank-line separated or section-like blocks)
    paragraphs = re.split(r'\n\s*\n|\n(?=[A-Z][A-Z\s]+\n)', resume_text)

    # Pattern: "X+ years" or "X years" or "X.Y+ years" (captures the number)
    year_pattern = re.compile(r'(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+of\s+(?:experience|expertise|success|professional)', re.IGNORECASE)

    for para in paragraphs:
        para_lower = para.lower()
        match = year_pattern.search(para)
        if not match:
            continue

        stated_years = float(match.group(1))

        # Check which skills are mentioned in this same paragraph
        # Handle plural/singular variations (e.g., "REST APIs" matches "REST API development")
        for skill in all_skills:
            skill_lower = skill.lower()
            # Direct match
            if skill_lower in para_lower:
                explicit_map[skill_lower] = stated_years
                continue
            # Strip trailing 's' for plural check (e.g., "REST APIs" → "REST API")
            if skill_lower.endswith("s") and skill_lower[:-1] in para_lower:
                explicit_map[skill_lower] = stated_years

    return explicit_map


def recalculate_experience(parsed_data: dict, resume_text: str = "") -> None:
    """Recalculate role years and total_years from start/end dates.

    Args:
        parsed_data: The parsed resume dict (mutated in place).
        resume_text: The original resume markdown text, used to detect
                     explicit summary-level year statements.
    """
    if not parsed_data or "experience" not in parsed_data:
        return

    roles = parsed_data["experience"].get("roles", [])
    if not roles:
        return

    intervals = []
    for role in roles:
        start_dt = _parse_date(role.get("start_date"), is_end_date=False)
        end_dt = _parse_date(role.get("end_date"), is_end_date=True)

        if start_dt and end_dt and start_dt <= end_dt:
            days = (end_dt - start_dt).days
            role["years"] = round(days / 365.25, 1)
            intervals.append([start_dt, end_dt])
        else:
            role["years"] = 0.0

    if not intervals:
        parsed_data["experience"]["total_years"] = 0.0
        return

    # Create a deep copy for merging so we don't mutate the original intervals mapped to roles
    sorted_intervals = sorted([[iv[0], iv[1]] for iv in intervals], key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    for current in sorted_intervals[1:]:
        last = merged[-1]
        if current[0] <= last[1]:
            last[1] = max(last[1], current[1])
        else:
            merged.append([current[0], current[1]])

    total_days = sum((iv[1] - iv[0]).days for iv in merged)
    parsed_data["experience"]["total_years"] = round(total_days / 365.25, 1)

    # Now, recalculate skill_experience deterministically
    skill_exp = parsed_data.get("skill_experience", [])
    if not skill_exp:
        return

    # Build the explicit summary-level skill→years mapping from the raw resume text
    all_skill_names = [s.get("skill", "") for s in skill_exp if s.get("skill")]
    summary_years = _extract_summary_skill_years(resume_text, all_skill_names)

    for skill_obj in skill_exp:
        skill_name = skill_obj.get("skill", "")
        if not skill_name:
            continue

        skill_name_lower = skill_name.lower()

        # If the LLM already gave it 0.0, keep it 0.0 (e.g. only in technical skills section)
        if skill_obj.get("years", 0.0) == 0.0:
            continue

        # PRIORITY 1: Explicit summary-level statement (e.g., "6+ years... Node.js")
        # Trust the candidate's explicit statement — even if it exceeds total_years
        # (they may have experience beyond the listed roles).
        if skill_name_lower in summary_years:
            skill_obj["years"] = summary_years[skill_name_lower]
            continue

        # PRIORITY 2: Role-based calculation for skills NOT mentioned in a summary statement
        skill_intervals = []
        for role, interval in zip(roles, intervals):
            # Check if skill is mentioned in this role's highlights
            highlights = " ".join(role.get("highlights", [])).lower()
            if skill_name_lower in highlights:
                # Add a copy of the interval to prevent mutation
                skill_intervals.append([interval[0], interval[1]])

        if not skill_intervals:
            # If not found in any highlights, trust the LLM's explicit stated_years fallback
            continue

        # Merge overlapping intervals for this specific skill
        skill_intervals.sort(key=lambda x: x[0])
        merged_skill = [skill_intervals[0]]
        for current in skill_intervals[1:]:
            last = merged_skill[-1]
            if current[0] <= last[1]:
                last[1] = max(last[1], current[1])
            else:
                merged_skill.append([current[0], current[1]])

        skill_days = sum((iv[1] - iv[0]).days for iv in merged_skill)
        calculated_years = round(skill_days / 365.25, 1)

        original_years = skill_obj.get("years")

        # If the LLM's original output is very close (<= 1.0 years diff) to our strict math,
        # it means the LLM attempted the role-based calculation but made a mental math error.
        # We overwrite it to fix the math.
        # If the difference is large (> 1.0 years), the LLM likely found an EXPLICIT mention
        # (e.g., "Java (10 years)") which overrides the role calculation. We preserve it!
        if original_years is not None and abs(original_years - calculated_years) > 1.0:
            continue

        # Cap role-calculated years to total career duration (cannot exceed total_years)
        total_years = parsed_data["experience"].get("total_years", 0.0)
        if total_years and total_years > 0 and calculated_years > total_years:
            calculated_years = total_years

        skill_obj["years"] = calculated_years
