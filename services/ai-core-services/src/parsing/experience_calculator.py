"""Deterministic experience recalculation for parsed resume data.

Pure functions — no I/O. Overrides LLM date math with strict Python calculations.
When the resume explicitly ties years of experience to specific skills
(e.g., "10 years of experience in Java", "Python (5 years)"),
those explicit years take absolute priority over role-based calculations.
Generic summary statements ("7 years of professional experience") do NOT
blanket-assign years to all skills in the same paragraph — skills without
an explicit per-skill year statement fall back to role-based calculation.
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
    """Extract ONLY explicitly per-skill stated years from summary/description text.

    A skill gets years ONLY when the text explicitly associates years with
    that specific skill, e.g.:\
      - "10 years of experience in Java" → Java = 10.0
      - "5+ years of Python and React" → Python = 5.0, React = 5.0
      - "5-7 years of Python experience" → Python = 7.0 (max of range)
      - "Java (8 years)" → Java = 8.0

    Generic statements like "7 years of professional experience. Skilled in
    Jenkins, Docker" do NOT assign 7 years to Jenkins/Docker — those skills
    fall through to role-based calculation instead.

    Returns a dict mapping skill_name_lower -> explicit_years.
    """
    if not resume_text or not all_skills:
        return {}

    explicit_map: dict[str, float] = {}

    # Build a set of lower-cased skill names for fast lookup
    skill_set_lower = {s.lower() for s in all_skills}

    def _parse_year_value(low_str: str, high_str: str | None) -> float:
        """Return the year value to use. For ranges pick the higher number."""
        low = float(low_str)
        if high_str:
            return max(low, float(high_str))
        return low

    # --- Pattern A: "X[+] years" or "X-Y years" of experience in/with/using <skill list> ---
    # Handles:
    #   "10 years of experience in Java"
    #   "5+ years of expertise with Python and React"
    #   "5-7 years of experience in Java"  → picks 7.0
    pattern_a = re.compile(
        r'(\d+(?:\.\d+)?)'                                   # lower bound (group 1)
        r'(?:\s*[-–]\s*(\d+(?:\.\d+)?))?'                    # optional upper bound (group 2)
        r'\+?\s*(?:years?|yrs?)\s+of\s+'
        r'(?:experience|expertise|success|professional[\w\s]*?)'
        r'\s+(?:in|with|using|on|across)\s+'
        r'([^.;\n]+)',                                        # skill clause (group 3)
        re.IGNORECASE,
    )

    # --- Pattern C: "X[+] years" or "X-Y years" of <skill> experience ---
    # Handles:
    #   "5-7 years of Python experience"     → Python = 7.0
    #   "10 years of Java development"       → Java = 10.0
    #   "3+ years of React experience"       → React = 3.0
    pattern_c = re.compile(
        r'(\d+(?:\.\d+)?)'                                   # lower bound (group 1)
        r'(?:\s*[-–]\s*(\d+(?:\.\d+)?))?'                    # optional upper bound (group 2)
        r'\+?\s*(?:years?|yrs?)\s+of\s+'
        r'([^.;\n]{1,60})',                                   # short clause containing skill (group 3)
        re.IGNORECASE,
    )

    # --- Pattern B: "skill (X years)" or "skill - X years" inline format ---
    pattern_b = re.compile(
        r'([A-Za-z][A-Za-z0-9\s.#+/\-]*?)\s*'       # skill name (flexible)
        r'(?:\(|\-\s*|–\s*|:\s*)'                      # delimiter: (, -, –, :
        r'(\d+(?:\.\d+)?)'                              # lower bound (group 2)
        r'(?:\s*[-–]\s*(\d+(?:\.\d+)?))?'              # optional upper bound (group 3)
        r'\+?\s*(?:years?|yrs?)'
        r'(?:\)|)',                                      # optional closing )
        re.IGNORECASE,
    )

    def _skill_in_text(skill_lower: str, text_lower: str) -> bool:
        """Check if a skill name appears in text, handling plural/singular."""
        if skill_lower in text_lower:
            return True
        # Strip trailing 's' for plural check (e.g., "REST APIs" → "REST API")
        if skill_lower.endswith("s") and skill_lower[:-1] in text_lower:
            return True
        return False

    # Scan entire resume text for Pattern A matches
    # (years of experience IN/WITH/USING <skills>)
    for match in pattern_a.finditer(resume_text):
        stated_years = _parse_year_value(match.group(1), match.group(2))
        skill_clause = match.group(3).lower()

        for skill in all_skills:
            skill_lower = skill.lower()
            if _skill_in_text(skill_lower, skill_clause):
                explicit_map[skill_lower] = stated_years

    # Scan entire resume text for Pattern C matches
    # (X years of <skill> experience — skill is in the clause, not after a preposition)
    for match in pattern_c.finditer(resume_text):
        stated_years = _parse_year_value(match.group(1), match.group(2))
        skill_clause = match.group(3).lower()

        # Only assign if a known skill is directly named in the short clause
        # AND the clause does NOT contain generic words that mean it's a broad statement
        generic_words = {"professional", "software", "engineering", "industry", "work", "career", "total"}
        if any(w in skill_clause for w in generic_words):
            continue

        for skill in all_skills:
            skill_lower = skill.lower()
            if _skill_in_text(skill_lower, skill_clause):
                # Only assign if not already set by Pattern A (Pattern A is more precise)
                if skill_lower not in explicit_map:
                    explicit_map[skill_lower] = stated_years

    # Scan entire resume text for Pattern B matches (inline format)
    for match in pattern_b.finditer(resume_text):
        candidate_skill = match.group(1).strip()
        stated_years = _parse_year_value(match.group(2), match.group(3))
        candidate_lower = candidate_skill.lower()

        for skill in all_skills:
            skill_lower = skill.lower()
            if skill_lower in candidate_lower or candidate_lower in skill_lower:
                explicit_map[skill_lower] = stated_years

    return explicit_map


_INTERNSHIP_RE = re.compile(r'\binterns?\b|\binternship\b', re.IGNORECASE)
_MIN_INTERNSHIP_MONTHS = 6


def _is_internship_role(role: dict) -> bool:
    """Detect whether a role is an internship based on its title or the LLM flag."""
    if role.get("is_internship"):
        return True
    title = role.get("title") or ""
    return bool(_INTERNSHIP_RE.search(title))


def recalculate_experience(parsed_data: dict, resume_text: str = "") -> None:
    """Recalculate role years and total_years from start/end dates.

    Internship roles (>= 6 months) are kept in the parsed data for display
    but are excluded from ``total_years`` and ``skill_experience`` so they
    do not affect scoring.  Internships shorter than 6 months are removed.

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

    # ------------------------------------------------------------------
    # Phase 1: Compute each role's years & deterministic is_internship flag
    # ------------------------------------------------------------------
    all_intervals: list[list] = []          # parallel to *roles* (after pruning)
    non_intern_intervals: list[list] = []   # only non-internship intervals
    non_intern_roles: list[dict] = []       # only non-internship roles

    roles_to_keep: list[dict] = []

    for role in roles:
        start_dt = _parse_date(role.get("start_date"), is_end_date=False)
        end_dt = _parse_date(role.get("end_date"), is_end_date=True)

        if start_dt and end_dt and start_dt <= end_dt:
            days = (end_dt - start_dt).days
            role["years"] = round(days / 365.25, 1)
        else:
            role["years"] = 0.0
            start_dt = None
            end_dt = None

        is_intern = _is_internship_role(role)
        role["is_internship"] = is_intern

        if is_intern:
            # Remove internships shorter than 6 months
            months = (role.get("years") or 0.0) * 12
            if months < _MIN_INTERNSHIP_MONTHS:
                continue  # drop this role entirely

        roles_to_keep.append(role)

        if start_dt and end_dt:
            interval = [start_dt, end_dt]
            all_intervals.append(interval)
            if not is_intern:
                non_intern_intervals.append(interval)
                non_intern_roles.append(role)
        else:
            all_intervals.append(None)
            if not is_intern:
                non_intern_intervals.append(None)
                non_intern_roles.append(role)

    # Replace roles list with the pruned version (short internships removed)
    parsed_data["experience"]["roles"] = roles_to_keep
    roles = roles_to_keep

    # ------------------------------------------------------------------
    # Phase 2: total_years from NON-internship roles only
    # ------------------------------------------------------------------
    valid_non_intern = [iv for iv in non_intern_intervals if iv is not None]
    if not valid_non_intern:
        parsed_data["experience"]["total_years"] = 0.0
        # Still need to handle skill_experience below
    else:
        sorted_intervals = sorted([[iv[0], iv[1]] for iv in valid_non_intern], key=lambda x: x[0])
        merged = [sorted_intervals[0]]
        for current in sorted_intervals[1:]:
            last = merged[-1]
            if current[0] <= last[1]:
                last[1] = max(last[1], current[1])
            else:
                merged.append([current[0], current[1]])

        total_days = sum((iv[1] - iv[0]).days for iv in merged)
        parsed_data["experience"]["total_years"] = round(total_days / 365.25, 1)

    # ------------------------------------------------------------------
    # Phase 3: skill_experience from NON-internship roles only
    # ------------------------------------------------------------------
    skill_exp = parsed_data.get("skill_experience", [])
    if not skill_exp:
        return

    # Build the explicit summary-level skill→years mapping from the raw resume text
    all_skill_names = [s.get("skill", "") for s in skill_exp if s.get("skill")]
    summary_years = _extract_summary_skill_years(resume_text, all_skill_names)

    # Build parallel list of valid intervals for non-internship roles only
    scoring_intervals = [iv for iv in non_intern_intervals if iv is not None]

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

        # PRIORITY 2: Role-based calculation — NON-INTERNSHIP roles only
        skill_intervals = []
        for role, interval in zip(non_intern_roles, scoring_intervals):
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
