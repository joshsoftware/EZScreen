JD_PROMPT_TEMPLATE = """
You are an expert job description parser. Parse this JD systematically.
Return ONLY a JSON object in this format:
{
  "title": null,
  "company": null,
  "company_description": null,
  "experience_required": {
    "min_years": null,
    "max_years": null
  },
  "skills": {
    "must_have": [
      {"skill": "skill1", "required_years": null},
      {"skill": "skill2", "required_years": 3.0}
    ],
    "good_to_have": [
      {"skill": "skill1", "required_years": null}
    ]
  },
  "qualifications": ["degree1", "degree2"],
  "responsibilities": ["resp1", "resp2"],
  "location": null,
  "employment_type": "Full-time"
}

### Extraction Rules:
- For `must_have` and `good_to_have` skills, if the JD explicitly states a number of years of experience required for that specific skill (e.g., "3 years of Java"), set `required_years` to that number.
- If no specific years are mentioned for that individual skill, set `required_years` to `null`. Do not automatically assume the global `min_years` applies unless explicitly stated.

### Job Description Text:
__JD_TEXT__
"""


class JDPromptBuilder:
    """Builds the LLM prompt for job description parsing."""

    def build(self, jd_text: str) -> str:
        return JD_PROMPT_TEMPLATE.replace("__JD_TEXT__", jd_text)


jd_prompt_builder = JDPromptBuilder()
