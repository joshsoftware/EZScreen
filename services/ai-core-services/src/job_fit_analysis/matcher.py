import json
from src.llm.client import OllamaClient
from src.core.logger import logger
from src.parsing.schemas import ParsedResumeData, ParsedJDData

class JobFitMatcher:
    def __init__(self):
        self.llm_client = OllamaClient()

    async def analyze_fit(self, resume_data: ParsedResumeData, jd_data: ParsedJDData) -> dict:
        """Compares the parsed resume against the parsed JD using LLM."""
        try:
            prompt = self._build_matching_prompt(resume_data, jd_data)
            
            logger.info("Sending job fit analysis prompt to LLM")
            response = await self.llm_client.openai_chat_generate(prompt=prompt, temperature=0.1, timeout=120.0)
            
            raw_json = response.response.strip()
            
            # Basic cleanup in case LLM wraps it in markdown blocks
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
                
            match_result = json.loads(raw_json.strip())
            return match_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Matcher JSON output: {e}\nRaw Output: {response.response}")
            raise ValueError("LLM returned invalid matching JSON")
        except Exception as e:
            logger.error(f"Unexpected error during matching: {e}")
            raise

    def _build_matching_prompt(self, resume_data: ParsedResumeData, jd_data: ParsedJDData) -> str:
        prompt = """
You are an expert technical recruiter and data analyst.
Compare the given candidate resume with the job description and calculate a match score based strictly on the predefined evaluation criteria below.
Return STRICT JSON only, no commentary.

### Candidate Resume (parsed JSON):
__RESUME_JSON__

### Job Description (parsed JSON):
__JD_JSON__

### Predefined Evaluation Criteria (Total: 100 Points)

1. Must-Have Skills (40 Points):
   - Calculate the percentage of JD must-have skills found in the resume.
   - Multiply that percentage by 40.
   - A skill is considered found when there is explicit evidence in the candidate's primary_skills, secondary_skills, or experience.
   - Normalize equivalent technology names before matching.
   - Do not infer a skill from a job title.
   - Do not consider a related but different technology as a match unless it is explicitly equivalent.

2. Relevant Experience (30 Points):
   - Calculate Relevant Experience based primarily on the candidate's professional experience with the JD's MUST-HAVE skills.
   - For each JD must-have skill, use experience.roles[].highlights and the corresponding role dates/years to determine the candidate's professional experience with that skill.
   - A skill counts as professional experience only when the role's highlights explicitly show that the candidate used or worked with that skill.
   - Do not use primary_skills or secondary_skills alone to determine years of professional experience.
   - Do not infer experience from a job title.
   - If the same must-have skill appears in multiple roles, combine the relevant periods without double-counting overlapping periods.
   - If the candidate has no role-specific evidence for a must-have skill, candidate_years = 0.0.
   - If the JD specifies required years for an individual must-have skill:
       skill_experience_ratio = min(candidate_years / required_years, 1.0)
   - If the JD does not specify required years for an individual must-have skill:
       skill_experience_ratio = 1.0 if meaningful professional experience exists, otherwise 0.0.
   - IMPORTANT: The JD's overall min_experience_years must NOT be copied into required_years for individual must-have skills.
   - required_years must be null when the JD does not explicitly specify years for that particular skill.
   - Calculate relevant_experience_percentage as the average of the skill_experience_ratio values across all JD must-have skills.
   - Calculate experience_score as:
       relevant_experience_percentage × 30
   - Round experience_score to 2 decimal places.
   - Do not use the candidate's total_years alone to award experience points. The score must reflect experience with the JD's must-have skills.

3. Good-to-Have Skills (20 Points):
   - Calculate the percentage of JD good-to-have skills found in the resume.
   - Multiply that percentage by 20.
   - Normalize equivalent technology names before matching.
   - A skill is considered found when there is explicit evidence in the candidate's primary_skills, secondary_skills, or experience.
   - Do not infer a skill from a job title.
   - Do not consider a related but different technology as a match unless it is explicitly equivalent.

4. Qualifications & Domain (Maximum 10 Points):
   - Award 10 points if they have at least one exact degree/qualification match.
   - Award 5 points if their best match is a somewhat related field.
   - Award 5 points if they have a relevant certificate that comes under qualifications.
   - Award 0 points if completely unrelated and lacking relevant certificates.
   - Consider domain expertise if relevant to the JD.
   - Do not infer qualifications or domain expertise that are not explicitly stated in the candidate resume.

### Must-Have Skill Experience Analysis:

For every JD must-have skill:

- Identify whether the skill is explicitly present in the candidate's professional experience.
- Use experience.roles[].highlights as the primary evidence.
- Use the corresponding role dates/years to calculate candidate_years.
- Do not assume that a skill was used throughout an entire role unless the role's highlights explicitly support that usage.
- Do not assume that a skill listed in primary_skills or secondary_skills was used for the candidate's entire career.
- Do not transfer experience from one technology to another related technology.
- If the same skill is demonstrated in multiple roles, combine the relevant periods without double-counting overlapping periods.
- The same role duration may contribute to multiple different must-have skills when the role explicitly demonstrates use of each skill.
- If no professional evidence exists for a must-have skill, candidate_years must be 0.0.
- If the dates are insufficient to calculate candidate_years reliably, use null rather than guessing.
- required_years must come ONLY from an explicit experience requirement for that specific must-have skill in the current JD.
- Never copy required_years from another candidate, another JD, another matching result, or any example.
- If the current JD specifies only an overall min_experience_years, do not use that value as required_years for every must-have skill.

### Overall Experience Match:

- Check the candidate's total_years against the JD's overall min_experience_years when the JD provides an overall experience requirement.
- If the candidate's total_years is greater than or equal to the JD's overall min_experience_years, the overall experience requirement is satisfied.
- If the JD does not specify an overall minimum experience requirement, do not assume one.
- experience_match should be true when the candidate satisfies the JD's explicitly stated overall experience requirement.
- If the JD specifies skill-specific experience requirements, also consider whether the candidate meets those requirements.
- Do not mark experience_match as false solely because the candidate is missing a must-have skill when that skill has no explicitly stated experience-year requirement. Skill gaps are already reflected in must_have_skills_score and experience_score.

### Overall Score:

- Calculate each of the four predefined criteria independently.
- Must-Have Skills = maximum 40 points.
- Relevant Experience = maximum 30 points.
- Good-to-Have Skills = maximum 20 points.
- Qualifications & Domain = maximum 10 points.
- Sum the four scores to obtain the total score out of 100.
- Convert the total score to a 0.0–10.0 scale:
    match_score = total_score / 10
- Round match_score to 2 decimal places.
- Do not change the predefined weighting of 40 + 30 + 20 + 10 = 100.

### Matched and Missing Skills:

- matched_skills.must_have must contain JD must-have skills for which the candidate has explicit evidence.
- matched_skills.good_to_have must contain JD good-to-have skills for which the candidate has explicit evidence.
- missing_skills.must_have must contain JD must-have skills for which there is no explicit evidence.
- missing_skills.good_to_have must contain JD good-to-have skills for which there is no explicit evidence.
- Do not mark a skill as matched solely because another related technology is present.
- Normalize equivalent technology names before determining matches.

### Reasoning:

- Output 2–4 concise reasoning points.
- Focus on the strongest factors affecting the match.
- Mention important must-have skill matches, relevant experience strengths, experience gaps, qualifications, or missing requirements.
- Do not include unsupported claims.

### Final Validation:

Before returning the JSON, verify that:

- must_have_skills_score is between 0 and 40.
- experience_score is between 0 and 30.
- good_to_have_skills_score is between 0 and 20.
- qualifications_score is between 0 and 10.
- The four scores sum to a total between 0 and 100.
- match_score equals total_score / 10.
- Relevant Experience was calculated from the candidate's demonstrated experience with JD must-have skills.
- Role highlights were used as the primary evidence for skill-specific professional experience.
- required_years is null unless the current JD explicitly specifies years for that specific skill.
- The JD's overall min_experience_years was not incorrectly copied into skill-specific required_years.
- Overlapping experience periods for the same skill were not double-counted.
- No technology was inferred from a job title.
- No unsupported experience was added.
- All numeric scores are numbers, not strings.
- The output is valid JSON only.

### Output Format (STRICT JSON):

{
  "score_breakdown": {
    "must_have_skills_score": 30.0,
    "experience_score": 22.5,
    "good_to_have_skills_score": 0.0,
    "qualifications_score": 10.0
  },
  "match_score": 6.25,
  "reasoning": [
    "Candidate possesses 3 out of 4 must-have skills.",
    "Candidate has demonstrated professional experience with Python, FastAPI, and Docker, but no role-specific experience with Kubernetes.",
    "The candidate meets the JD's overall minimum experience and qualification requirements."
  ],
  "matched_skills": {
    "must_have": ["Python", "FastAPI", "Docker"],
    "good_to_have": []
  },
  "missing_skills": {
    "must_have": ["Kubernetes"],
    "good_to_have": ["AWS", "GraphQL"]
  },
  "must_have_experience": [
    {
      "skill": "Python",
      "required_years": null,
      "candidate_years": 4.5,
      "skill_experience_ratio": 1.0,
      "meets_requirement": true
    },
    {
      "skill": "FastAPI",
      "required_years": null,
      "candidate_years": 4.5,
      "skill_experience_ratio": 1.0,
      "meets_requirement": true
    },
    {
      "skill": "Docker",
      "required_years": null,
      "candidate_years": 4.5,
      "skill_experience_ratio": 1.0,
      "meets_requirement": true
    },
    {
      "skill": "Kubernetes",
      "required_years": null,
      "candidate_years": 0.0,
      "skill_experience_ratio": 0.0,
      "meets_requirement": false
    }
  ],
  "qualification_match": true,
  "experience_match": true
}
"""
        prompt = prompt.replace("__RESUME_JSON__", json.dumps(resume_data.model_dump(), indent=2))
        prompt = prompt.replace("__JD_JSON__", json.dumps(jd_data.model_dump(), indent=2))
        return prompt

job_fit_matcher = JobFitMatcher()
