"""Deterministic experience recalculation for parsed resume data.

Pure functions — no I/O. Overrides LLM date math with strict Python calculations.
"""

from __future__ import annotations

import calendar
import datetime


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


def recalculate_experience(parsed_data: dict) -> None:
    """Recalculate role years and total_years from start/end dates."""
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

    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for current in intervals[1:]:
        last = merged[-1]
        if current[0] <= last[1]:
            last[1] = max(last[1], current[1])
        else:
            merged.append(current)

    total_days = sum((iv[1] - iv[0]).days for iv in merged)
    parsed_data["experience"]["total_years"] = round(total_days / 365.25, 1)
