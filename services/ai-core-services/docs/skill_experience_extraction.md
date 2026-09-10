# Skill Experience Year Extraction — Case Reference

Source: [`experience_calculator.py → _extract_summary_skill_years()`](../src/parsing/experience_calculator.py)

---

## ✅ Cases That ASSIGN Years from Summary

### Pattern A — `"X years of experience in/with/using/on/across [skills]"`

The year clause captures all text **after the preposition** up to the next `.` `;` or newline.
Only skills **explicitly named inside that clause** get the years assigned.

| Text | Result |
|---|---|
| `"10 years of experience in Java"` | Java = 10.0 |
| `"5+ years of experience in Python and React"` | Python = 5.0, React = 5.0 |
| `"10 years of experience in Java, Python, React"` | Java = 10.0, Python = 10.0, React = 10.0 |
| `"3+ years of experience using Java, Spring Boot"` | Java = 3.0, Spring Boot = 3.0 |
| `"7 years of expertise with Node.js"` | Node.js = 7.0 |
| `"5 years of experience on AWS and Docker"` | AWS = 5.0, Docker = 5.0 |
| `"8 years of expertise across REST APIs"` | REST APIs = 8.0 |
| `"5-7 years of experience in Java"` | Java = **7.0** *(max of range)* |
| `"3-5 years of experience with Python and React"` | Python = **5.0**, React = **5.0** *(max of range)* |

---

### Pattern B — Inline format `"skill (X years)"` / `"skill - X years"`

The skill name directly precedes the year value with a delimiter `(`, `-`, `–`, or `:`.

| Text | Result |
|---|---|
| `"Java (8 years)"` | Java = 8.0 |
| `"Python (3 years)"` | Python = 3.0 |
| `"Java - 8 years"` | Java = 8.0 |
| `"Java – 5 years"` | Java = 5.0 |
| `"Java: 10 years"` | Java = 10.0 |
| `"Java (5-8 years)"` | Java = **8.0** *(max of range)* |
| `"Python (2-3 years)"` | Python = **3.0** *(max of range)* |

---

### Pattern C — `"X years of [skill] experience/development"`

The year phrase comes first, followed by a short clause containing the skill name.
Only triggers when Pattern A doesn't match (no preposition), and the clause doesn't contain generic words.

| Text | Result |
|---|---|
| `"5-7 years of Python experience"` | Python = **7.0** *(max of range)* |
| `"10 years of Java development"` | Java = 10.0 |
| `"3+ years of React experience"` | React = 3.0 |

---

### Number Formats Supported (all patterns)

| Format | Example | Behaviour |
|---|---|---|
| Integer | `5 years` | 5.0 |
| Decimal | `3.5 years` | 3.5 |
| Plus sign | `5+ years` | 5.0 |
| Range | `5-7 years` | **7.0** (picks max) |

---

## ❌ Cases That Do NOT Assign from Summary → Fall Back to Role-Based

When no explicit per-skill year statement is found, each skill's years are calculated by summing
the durations of all **non-internship roles** whose highlights explicitly mention that skill.

| Text | What summary assigns | What the skills actually get |
|---|---|---|
| `"7 years of success in DevOps. Skilled in Jenkins, Docker"` | DevOps = 7.0 ✅ | Jenkins = sum of non-internship role durations where Jenkins appears in highlights |
| | | Docker = sum of non-internship role durations where Docker appears in highlights |
| `"10 years of professional experience. Technologies: React, Node.js"` | Nothing | React = sum of non-internship role durations where React appears in highlights |
| | | Node.js = sum of non-internship role durations where Node.js appears in highlights |
| `"5-7 years of professional experience. Skilled in React"` | Nothing | React = sum of non-internship role durations where React appears in highlights |
| `"10 years of software engineering experience"` | Nothing | All skills = sum of non-internship role durations where each skill appears in highlights |
| `"Over a decade of Java experience"` | Nothing *(no digit)* | Java = sum of non-internship role durations where Java appears in highlights |

> **Note:** "Fall back to role-based" is **not** zero. It calculates from actual work history.
> A skill only gets `0.0` if it never appears in any non-internship role's highlights.

---

### Generic Words That Block Pattern C

If any of these words appear in the Pattern C clause, the match is discarded to avoid false assignments:

`professional` · `software` · `engineering` · `industry` · `work` · `career` · `total`

**Example:** `"10 years of software engineering experience"` → blocked because `"software"` is in the
clause → all skills fall back to role-based.

---

## 🎓 Internship Handling

Source: [`experience_calculator.py → recalculate_experience()`](../src/parsing/experience_calculator.py)  
Prompt rules: [`prompt_builder.py → CRITICAL RULE - INTERNSHIPS`](../src/parsing/prompt_builder.py)

---

### Duration-Based Threshold

| Internship Duration | Behaviour |
|---|---|
| **< 6 months** | Completely removed from parsed data. Treated as if it does not exist. |
| **≥ 6 months** | Kept in the `roles` list for display. Excluded from all scoring calculations. |

---

### What Internships (≥ 6 months) Affect vs. Don't Affect

| Field | Internship included? |
|---|---|
| `experience.roles` (display list) | ✅ Yes — visible in the parsed output |
| `experience.total_years` | ❌ No — internship duration is excluded |
| `skill_experience[].years` | ❌ No — internship highlights are not used |
| `primary_skills` / `secondary_skills` | ❌ No — no skills extracted from internship descriptions |

---

### Detection Logic (Two Layers)

#### Layer 1 — LLM Prompt
The prompt instructs the LLM to:
- Calculate the internship duration from `start_date` / `end_date`
- Skip internships **< 6 months** entirely (don't extract)
- Extract internships **≥ 6 months** as a normal role
- Do NOT include any internship duration in `total_years` or `skill_experience`
- Do NOT extract skills from internship descriptions into `primary_skills` / `secondary_skills`

#### Layer 2 — Deterministic Python Code (safety net)
Even if the LLM makes a mistake, `recalculate_experience()` enforces the rules:


- Detects internship roles by matching `"Intern"` / `"Internship"` in the **role title**
- Computes the role's actual duration in months (`years × 12`)
- Drops the role entirely if duration < 6 months
- Excludes internship roles from the `total_years` interval merge
- Excludes internship role highlights from the skill experience calculation

---

### Internship Case Examples

| Scenario | Duration | Outcome |
|---|---|---|
| `"Software Engineering Intern"` (Jan–Apr 2023) | 3 months | ❌ Removed entirely |
| `"Backend Intern"` (Jan–Aug 2023) | 7 months | ✅ Kept in roles, excluded from scoring |
| `"Software Developer Intern"` (Aug 2019–Feb 2020) | 6 months | ✅ Kept in roles, excluded from scoring |
| `"Engineer Trainee"` | Any | ✅ Treated as full professional experience (not an internship) |

---

### Scoring Isolation — End-to-End

```
resume has: 3 years full-time + 1 year internship
                                 ↓
total_years          → 3.0   (internship excluded)
skill_experience     → calculated from 3-year role only
score_calculator.py  → uses total_years and skill_experience → unaffected by internship
```

> **Note:** `score_calculator.py` and `matcher.py` are **not modified**. 
