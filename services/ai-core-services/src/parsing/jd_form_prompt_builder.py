"""Prompt to map raw JD text into Create Job form sections."""

JD_FORM_PREFILL_PROMPT = """
You are an expert job description parser for a structured hiring form.
Extract ONLY what is explicitly in the JD. Return ONE valid JSON object — no markdown.

### Target schema
{
  "title": null,
  "location": null,
  "job_type": null,
  "work_type": null,
  "experience_min": null,
  "experience_max": null,
  "role_summary": null,
  "about_company": null,
  "responsibilities": [],
  "must_have_skills_text": [],
  "good_to_have_skills_text": [],
  "qualifications": [],
  "domain_experience": [],
  "tools_stack": [],
  "needs_review": [
    { "label": "Benefits", "content": "..." }
  ]
}

### Field rules
- title: job title only.
- location: city / region / country string, or null.
- job_type: ONLY one of "full_time", "part_time", "contract", or null.
- work_type: ONLY one of "onsite", "hybrid", "remote", or null.
- experience_min / experience_max: numbers with at most one decimal (e.g. 2, 2.5, 5.7), or null.
- role_summary: short role overview / summary paragraph (plain text). Prefer "Role overview", "About the role", "Summary".
- about_company: company / team description. Prefer "About the company", "About us".
- responsibilities: array of bullet strings (one responsibility each).
- must_have_skills_text: array of strings from Must-have / Required / Requirements skill sections. Include years in the string when stated (e.g. "Java — 3 years").
- good_to_have_skills_text: array from Nice-to-have / Preferred / Good-to-have.
- qualifications: array of complete qualification lines (do not split one sentence at commas).
- domain_experience: industry / domain lines.
- tools_stack: tools & stack lines not already covered as must/good skills when the JD has a dedicated Tools section; otherwise [].

### needs_review (IMPORTANT)
Put content here when you are NOT confident which form section it belongs to, OR when it does not map to any field above.
Examples: Benefits, Compensation/salary, Perks, Culture, Equal opportunity / legal, How to apply, Travel, Visa, Interview process, misc headings, orphan paragraphs.
Each item: { "label": short heading or "Other", "content": plain text preserving bullets as newlines }.
Do NOT duplicate content that you already placed in a mapped field.
If everything maps cleanly, return "needs_review": [].

### General
- Never invent skills, years, or sections.
- Prefer section headings when present.
- Arrays must be arrays (use [] when empty). Scalars use null when missing.
- Preserve meaning; do not paraphrase into marketing fluff.

### Job Description Text:
__JD_TEXT__
"""


class JDFormPrefillPromptBuilder:
    def build(self, jd_text: str) -> str:
        return JD_FORM_PREFILL_PROMPT.replace("__JD_TEXT__", jd_text)


jd_form_prefill_prompt_builder = JDFormPrefillPromptBuilder()
