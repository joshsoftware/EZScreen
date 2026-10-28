"""Deterministic check of the LLM's matched / missing skills against the resume.

The LLM matches JD skills only against the extracted skill lists and is not
always consistent, so skills written in the resume (role bullets, internships,
projects) were reported missing, and concerns contradicted matched skills
(Bug-032). Pure functions — no I/O; runs before recalculate_scores.
"""

from __future__ import annotations

import re

# Other spellings of a skill, checked in addition to the skill itself.
_ALIASES: dict[str, tuple[str, ...]] = {
    "javascript": ("js", "ecmascript"),
    "typescript": ("ts",),
    "node.js": ("nodejs", "node js"),
    "react": ("react.js", "reactjs", "react js"),
    "react.js": ("react", "reactjs", "react js"),
    "vue.js": ("vue", "vuejs", "vue js"),
    "angular": ("angularjs", "angular.js"),
    "express.js": ("express", "expressjs"),
    "next.js": ("nextjs", "next js"),
    "mongodb": ("mongo",),
    "postgresql": ("postgres",),
    "postgres": ("postgresql",),
    "mysql": ("my sql",),
    "rest api": ("restful api", "restful"),
    "restful api": ("rest api", "restful"),
    "api integration": ("integrated api", "integrating api", "integrate api", "third-party api", "rest api", "restful api"),
    "api integrations": ("integrated api", "integrating api", "integrate api", "third-party api", "rest api", "restful api"),
    "aws": ("amazon web services",),
    "eks": ("elastic kubernetes service", "amazon eks", "aws eks"),
    "ecs": ("elastic container service",),
    "gcp": ("google cloud platform", "google cloud"),
    "azure": ("microsoft azure",),
    "kubernetes": ("k8s",),
    "k8s": ("kubernetes",),
    "ci/cd": ("cicd", "ci cd", "continuous integration"),
    "c#": ("c sharp", "csharp"),
    ".net": ("dotnet", "asp.net"),
    "redux": ("redux toolkit", "rtk"),
    "spring boot": ("springboot",),
}

_MISSING_WORDS = (
    "missing",
    "not found",
    "not mentioned",
    "no mention",
    "not listed",
    "absent",
    "does not have",
    "doesn't have",
    "does not list",
    "doesn't list",
)
_NO_EXPERIENCE_WORDS = ("lack", "no experience", "no professional", "no hands-on", "no work experience")

_NO_CONCERNS = "No major concerns identified."


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _term_pattern(term: str) -> re.Pattern:
    # Word-ish boundaries that also respect "+", "#" and "." so "java" doesn't
    # match "javascript" and "c" doesn't match "c++". Optional plural "s".
    return re.compile(r"(?<![a-z0-9+#])" + re.escape(term) + r"s?(?![a-z0-9+#])")


def skill_variants(skill: str) -> set[str]:
    """The JD skill, its parts and known aliases, lower-cased."""
    name = _norm(skill)
    variants = {name}
    # "JavaScript (ES6+)" -> "javascript"; "Kubernetes (EKS)" -> "kubernetes", "eks"
    outer = _norm(re.sub(r"\([^)]*\)", " ", name))
    if outer:
        variants.add(outer)
    for inner in re.findall(r"\(([^)]*)\)", name):
        for piece in re.split(r"[,/]", inner):
            if _norm(piece):
                variants.add(_norm(piece))
    # "MySQL/PostgreSQL", "AWS - EKS"
    for piece in re.split(r"\s*/\s*|\s+-\s+", outer or name):
        if _norm(piece) and _norm(piece) != (outer or name):
            variants.add(_norm(piece))
    for variant in list(variants):
        last = variant.split()[-1] if variant.split() else variant
        # "REST APIs" -> "rest api"; not "redis", "express", "aws".
        if (
            len(last) >= 4
            and last.endswith("s")
            and not last.endswith(("ss", "us"))
            and (not last.endswith("is") or last.endswith("apis"))
        ):
            variants.add(variant[:-1])
    for variant in list(variants):
        variants.update(_ALIASES.get(variant, ()))
    # Single letters / version tags alone are too ambiguous to search for.
    return {v for v in variants if len(v) >= 2 and not re.fullmatch(r"(es)?\d[\d.+]*", v)}


def mentions_skill(skill: str, text: str) -> bool:
    text = _norm(text)
    return any(_term_pattern(variant).search(text) for variant in skill_variants(skill))


def resume_evidence(resume: dict) -> str:
    """All resume text a skill can legitimately be found in."""
    parts: list[str] = []
    parts += resume.get("primary_skills") or []
    parts += resume.get("secondary_skills") or []
    parts += [item.get("skill", "") for item in resume.get("skill_experience") or [] if isinstance(item, dict)]
    experience = resume.get("experience") or {}
    for role in experience.get("roles") or []:
        parts += role.get("highlights") or []
        for group in role.get("highlight_groups") or []:
            parts.append(group.get("heading") or "")
            parts += group.get("highlights") or []
    for project in resume.get("projects") or []:
        parts.append(project.get("name") or "")
        parts += project.get("tech_stack") or []
        parts += project.get("highlights") or []
    return "\n".join(str(part) for part in parts if part)


def _candidate_years(skill: str, resume: dict) -> float | None:
    best = None
    for item in resume.get("skill_experience") or []:
        if not isinstance(item, dict) or item.get("years") is None:
            continue
        if mentions_skill(skill, item.get("skill", "")) or mentions_skill(item.get("skill", ""), skill):
            years = float(item["years"])
            best = years if best is None else max(best, years)
    return best


def _experience_entry(entries: list[dict], skill: str) -> dict | None:
    key = _norm(skill)
    return next((e for e in entries if isinstance(e, dict) and _norm(e.get("skill")) == key), None)


def _set_matched_experience(entries: list[dict], skill: str, required, resume: dict) -> None:
    entry = _experience_entry(entries, skill)
    if entry is None:
        entry = {"skill": skill}
        entries.append(entry)
    if required is not None:
        entry["required_years"] = required  # the JD is the source of truth
    entry.setdefault("required_years", None)
    years = _candidate_years(skill, resume)
    if years is not None:
        entry["candidate_years"] = years
    candidate = float(entry.get("candidate_years") or 0.0)
    required = entry.get("required_years")
    if required in (None, 0):
        ratio = 1.0
    else:
        ratio = min(1.0, candidate / float(required))
    entry["skill_experience_ratio"] = round(ratio, 2)
    entry["meets_requirement"] = ratio >= 1.0


def reconcile_skills(match_result: dict, resume: dict, jd: dict) -> None:
    """Move JD skills the resume does mention from missing to matched, give
    every JD skill exactly one experience entry, and drop concerns that
    contradict a matched skill. Never demotes a skill the LLM matched."""
    evidence = resume_evidence(resume)
    matched = match_result.setdefault("matched_skills", {})
    missing = match_result.setdefault("missing_skills", {})
    jd_skills = (jd or {}).get("skills") or {}

    for bucket, exp_key in (("must_have", "must_have_experience"), ("good_to_have", "good_to_have_experience")):
        requirements = [item for item in jd_skills.get(bucket) or [] if isinstance(item, dict) and item.get("skill")]
        if not requirements:
            continue
        llm_matched = {_norm(s) for s in matched.get(bucket) or []}
        entries = [e for e in match_result.get(exp_key) or [] if isinstance(e, dict)]
        new_matched: list[str] = []
        new_missing: list[str] = []
        for requirement in requirements:
            skill = requirement["skill"]
            if _norm(skill) in llm_matched:
                new_matched.append(skill)
            elif mentions_skill(skill, evidence):
                new_matched.append(skill)
                _set_matched_experience(entries, skill, requirement.get("required_years"), resume)
            else:
                new_missing.append(skill)
                if _experience_entry(entries, skill) is None:
                    entries.append(
                        {
                            "skill": skill,
                            "required_years": requirement.get("required_years"),
                            "candidate_years": 0.0,
                            "skill_experience_ratio": 0.0,
                            "meets_requirement": False,
                        }
                    )
        # One entry per JD skill, so score totals count every JD skill once.
        wanted = {_norm(r["skill"]) for r in requirements}
        seen: set[str] = set()
        cleaned = []
        for entry in entries:
            key = _norm(entry.get("skill"))
            if key in wanted and key not in seen:
                seen.add(key)
                cleaned.append(entry)
        matched[bucket] = new_matched
        missing[bucket] = new_missing
        match_result[exp_key] = cleaned

    _drop_contradicting_concerns(match_result)


def _drop_contradicting_concerns(match_result: dict) -> None:
    matched = match_result.get("matched_skills") or {}
    entries = (match_result.get("must_have_experience") or []) + (match_result.get("good_to_have_experience") or [])
    matched_skills = [s for bucket in ("must_have", "good_to_have") for s in matched.get(bucket) or []]
    missing = match_result.get("missing_skills") or {}
    missing_skills = [s for bucket in ("must_have", "good_to_have") for s in missing.get(bucket) or []]
    if not matched_skills:
        return

    def has_experience(skill: str) -> bool:
        entry = _experience_entry(entries, skill)
        return bool(entry) and float(entry.get("candidate_years") or 0.0) > 0

    kept = []
    for concern in match_result.get("concerns") or []:
        text = _norm(concern)
        contradicts = False
        if any(mentions_skill(skill, text) for skill in missing_skills):
            kept.append(concern)  # also about a genuinely missing skill
            continue
        for skill in matched_skills:
            if not mentions_skill(skill, text):
                continue
            if any(word in text for word in _MISSING_WORDS):
                contradicts = True
            elif any(word in text for word in _NO_EXPERIENCE_WORDS) and has_experience(skill):
                contradicts = True
        if not contradicts:
            kept.append(concern)
    if not kept and match_result.get("concerns"):
        kept = [_NO_CONCERNS]
    match_result["concerns"] = kept
