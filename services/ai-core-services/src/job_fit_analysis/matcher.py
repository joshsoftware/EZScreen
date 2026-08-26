import json
from src.llm.client import OllamaClient
from src.core.logger import logger
from src.parsing.schemas import ParsedResumeData, ParsedJDData
from src.common.llm_utils import parse_llm_json

class JobFitMatcher:
    def __init__(self):
        self.llm_client = OllamaClient()

    async def analyze_fit(self, resume_data: ParsedResumeData, jd_data: ParsedJDData) -> dict:
        """Compares the parsed resume against the parsed JD using LLM."""
        try:
            prompt = self._build_matching_prompt(resume_data, jd_data)
            
            logger.info("Sending job fit analysis prompt to LLM")
            response = await self.llm_client.openai_chat_generate(prompt=prompt, temperature=0.1, timeout=120.0)
            
            match_result = parse_llm_json(response.response)
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
   - A skill is considered found (and MUST be placed in `matched_skills`) if it is present anywhere in the candidate's `primary_skills` or `secondary_skills` arrays, REGARDLESS of whether they have 0.0 years of experience with it. If they listed it, they possess the baseline skill.
   - Normalize equivalent technology names before matching.
   - Do not infer a skill from a job title.

2. Relevant Experience (30 Points Total: 20 for Must-Have, 10 for Good-To-Have):
   - Calculate Relevant Experience by comparing the candidate's `skill_experience` array with the JD's must-have and good-to-have skill requirements.
   - For each JD skill, identify the candidate's candidate_years from the parsed_resume's `skill_experience` array. If the skill is not in the array, candidate_years = 0.0.
   - Calculate the skill_experience_ratio for each JD skill using these rules:
     * If the required experience is NOT mentioned in the JD for a particular skill AND the candidate possesses the skill (i.e., it is in matched_skills): give ratio as 1.0 (even if candidate_years is 0.0)
     * If the candidate does NOT possess the skill (i.e., it is in missing_skills): give ratio as 0.0
     * If the required experience IS mentioned in the JD for a particular skill and the candidate has LESS experience than required: give ratio as candidate_years / required_years
     * If the required experience IS mentioned in the JD for a particular skill and the candidate has MORE or EQUAL experience than required: give ratio as 1.0
   - Calculate must-have experience strictly using this exact formula:
     must_have_experience_score = (Sum of all skill_experience_ratios for must-have skills / total number of must-have skills) * 20
   - Calculate good-to-have experience strictly using this exact formula:
     good_to_have_experience_score = (Sum of all skill_experience_ratios for good-to-have skills / total number of good-to-have skills) * 10
     (If there are no good-to-have skills in the JD, good_to_have_experience_score = 10)
   - raw_experience = must_have_experience_score + good_to_have_experience_score
   - Round raw_experience to 2 decimal places.
   - For each skill in `must_have_experience` and `good_to_have_experience`, set `meets_requirement` to `true` ONLY IF `skill_experience_ratio` >= 1.0, otherwise `false`.
   - Set `experience_match` to `true` ONLY IF `raw_experience` is >= 20.0. Otherwise, set it to `false`.

3. Good-to-Have Skills (20 Points):
   - Calculate the percentage of JD good-to-have skills found.
   - Multiply that percentage by 20.
   - A skill is considered found (and MUST be placed in `matched_skills`) if it is present anywhere in the candidate's `primary_skills` or `secondary_skills` arrays, REGARDLESS of whether they have 0.0 years of experience with it.
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
2. Calculate Relevant Experience specifically using the candidate's `skill_experience` array against the JD's must-have and good-to-have skills and their required years.
3. Systematically calculate the raw score for each of the 4 criteria based on their respective weights (40, 30, 20, 10).
4. CRITICAL: Output the raw scores first, then convert them into a consolidated, out-of-10.0 scale for the `score_breakdown`:
   - `raw_must_have_skills`: max 40.0
   - `raw_good_to_have_skills`: max 20.0
   - `raw_experience`: max 30.0
   - `raw_qualifications`: max 10.0
   - `skills_score` = (raw_must_have_skills + raw_good_to_have_skills) / 6
   - `experience_score` = raw_experience / 3
   - `qualifications_score` = raw_qualifications / 1
   (e.g., if raw_must_have_skills is 32.0 and raw_good_to_have_skills is 15.0, skills_score is 7.83)
5. Calculate the final `match_score` out of 10.0 based on the total raw points: match_score = (raw_must_have_skills + raw_experience + raw_good_to_have_skills + raw_qualifications) / 10.
6. Output highly detailed analysis in plain, human-readable language suitable for a non-technical recruiter. DO NOT use technical terms like "ratio", "score", "formula", "0.0", or "1.0". Instead, write naturally. Provide the analysis in three parts:
   - `reasoning`: 3-4 bullet points summarizing the overall fit (e.g. "The candidate matches all core must-have skills...", "Qualification requirements fully met...").
   - `strengths`: 4-5 bullet points highlighting the candidate's strongest alignments with the JD (e.g. "Strong Java experience with over 14 years...", "Extensive domain expertise in Fintech...").
   - `concerns`: 4-5 bullet points highlighting gaps, missing skills, or shortfalls in experience. Crucially, if the JD requires a balanced skill set (e.g. Full Stack requiring 3 years) but the candidate's experience is heavily skewed (e.g. 3 years frontend, but only 2 months backend), you MUST explicitly point out this imbalance as a concern. (e.g. "Experience gap in Spring Boot: the candidate has 2 years, but the job requires at least 3 years...", "Imbalanced Full Stack experience: Candidate has 3 years of React, but only 2 months of Node.js backend experience against a 3-year requirement."). If no concerns, provide 1 bullet saying "No major concerns identified."
7. CRITICAL RULE: Never put a skill in `missing_skills` if it exists in `primary_skills` or `secondary_skills`, even if the candidate has 0.0 years of experience with it. If it is in their skills array, it MUST go into `matched_skills`.

### Output Format (STRICT JSON):

{
  "score_breakdown": {
    "raw_must_have_skills": 32.0,
    "raw_good_to_have_skills": 15.0,
    "raw_experience": 24.5,
    "raw_qualifications": 10.0,
    "skills_score": 7.83,
    "experience_score": 8.16,
    "qualifications_score": 10.0
  },
  "match_score": 8.15,
  "reasoning": [
    "Overall strong fit with technical alignment across most core skills.",
    "Qualification requirements fully met with a Bachelor's degree in Computer Science.",
    "Slight gaps in cloud infrastructure experience, but solid foundation in backend development."
  ],
  "strengths": [
    "The candidate matches core must-have skills including Java, Python, and SQL.",
    "Strong hands-on experience in Java (14 years), well exceeding the job requirements.",
    "Good coverage of nice-to-have skills, with practical experience in Docker and Kubernetes.",
    "Extensive domain expertise in E-commerce architecture."
  ],
  "concerns": [
    "Missing critical must-have skill: AWS — not found anywhere in the candidate's resume.",
    "Experience gap in Spring Boot: the candidate has 2 years of hands-on experience, but the role requires at least 3 years.",
    "Imbalanced experience for a Full Stack role: candidate has 4 years of frontend (React) experience, but only 3 months of backend (Node.js) experience.",
    "The candidate lists PostgreSQL as a skill but has no professional work experience using it in any of their roles."
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
    }
  ],
  "good_to_have_experience": [
    {
      "skill": "Docker",
      "required_years": null,
      "candidate_years": 2.0,
      "skill_experience_ratio": 1.0,
      "meets_requirement": true
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
