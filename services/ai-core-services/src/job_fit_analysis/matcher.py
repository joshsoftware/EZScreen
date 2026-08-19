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

2. Relevant Experience (30 Points):
   - Calculate Relevant Experience ONLY by comparing the candidate's professional experience with the JD's MUST-HAVE skills and their required years.
   - For each JD must-have skill, identify the candidate's experience with that skill using experience.roles[].highlights and the corresponding role dates/years.
   - A skill counts as professional experience if the role's title or highlights show that the candidate used it, or if it can be strongly inferred that they applied this skill during that role.
   - Do not use primary_skills or secondary_skills alone to determine years of experience without matching it to a specific role.
   - If the same must-have skill appears in multiple roles, combine the relevant experience periods without double-counting overlapping periods.
   - If the candidate has no role-specific evidence for a required must-have skill, candidate_years = 0.0.
   - Calculate the skill_experience_ratio for each JD must-have skill using these rules:
     * If the required experience is NOT mentioned in the JD for a particular skill and the candidate HAS experience: give ratio as 1.0
     * If the required experience is NOT mentioned in the JD for a particular skill and the candidate has NO experience: give ratio as 0.0
     * If the required experience IS mentioned in the JD for a particular skill and the candidate has LESS experience than required: give ratio as candidate_years / required_years
     * If the required experience IS mentioned in the JD for a particular skill and the candidate has MORE or EQUAL experience than required: give ratio as 1.0
   - Calculate experience_score strictly using this exact formula:
     experience_score = (Sum of all skill_experience_ratios / total number of must-have skills) * 30
   - Round experience_score to 2 decimal places.
   - For each skill in must_have_experience, set `meets_requirement` to `true` ONLY IF `skill_experience_ratio` >= 1.0, otherwise `false`.
   - Set `experience_match` to `true` if at least 75% of the must-have skills have `meets_requirement` set to `true`. Otherwise, set it to `false`.
   - Do not use the candidate's total_years alone to award experience points. The score must reflect experience specifically with the JD's must-have skills.

3. Good-to-Have Skills (20 Points):
   - Calculate the percentage of JD good-to-have skills found.
   - Multiply that percentage by 20.
   - Normalize equivalent technology names before matching.
   - Do not infer a skill from a job title.

4. Qualifications & Domain (Maximum 10 Points):
   - Award 10 points if they have at least one exact degree/qualification match.
   - Award 5 points if their best match is a somewhat related field.
   - Award 5 points if they have a relevant certificate that comes under qualifications.
   - Award 0 points if completely unrelated and lacking relevant certificates.
   - Consider domain expertise if relevant to the JD.
   - If the JD has no qualification requirements, qualifications_score = 10 and qualification_match = true.

### Instructions:

1. Compare candidate's skills with JD must-have and good-to-have skills.
2. Calculate Relevant Experience specifically from the candidate's experience with the JD's must-have skills and their required years.
3. Use role highlights and role dates/years as the evidence for skill-specific experience.
4. Systematically calculate the score for each of the 4 criteria.
5. Sum the scores to get a total out of 100.
6. Convert the total to a 0.0–10.0 scale:
   match_score = total_score / 10
7. Output reasoning in 2–4 short bullet points.
8. Do not change the predefined weighting: 40 + 30 + 20 + 10 = 100.

### Output Format (STRICT JSON):

{
  "score_breakdown": {
    "must_have_skills_score": 32.0,
    "experience_score": 24.5,
    "good_to_have_skills_score": 15.0,
    "qualifications_score": 10.0
  },
  "match_score": 8.15,
  "reasoning": [
    "Strong coverage of the JD's must-have skills.",
    "The candidate has relevant experience with most required skills but has less experience than required for one must-have skill.",
    "Qualifications and good-to-have skills are largely aligned with the JD."
  ],
  "matched_skills": {
    "must_have": ["..."],
    "good_to_have": ["..."]
  },
  "missing_skills": {
    "must_have": ["..."],
    "good_to_have": ["..."]
  },
  "must_have_experience": [
    {
      "skill": "Java",
      "required_years": 3.0,
      "candidate_years": 4.0,
      "skill_experience_ratio": 1.0,
      "meets_requirement": true
    },
    {
      "skill": "Spring Boot",
      "required_years": 3.0,
      "candidate_years": 2.0,
      "skill_experience_ratio": 0.67,
      "meets_requirement": false
    }
  ],
  "qualification_match": true,
  "experience_match": false
}
"""
        prompt = prompt.replace("__RESUME_JSON__", json.dumps(resume_data.model_dump(), indent=2))
        prompt = prompt.replace("__JD_JSON__", json.dumps(jd_data.model_dump(), indent=2))
        return prompt

job_fit_matcher = JobFitMatcher()
