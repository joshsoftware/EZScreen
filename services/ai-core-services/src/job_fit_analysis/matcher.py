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
        return f"""
You are an expert technical recruiter and data analyst.
Compare the given candidate resume with the job description and calculate a match score
based strictly on the predefined evaluation criteria below.
Return STRICT JSON only, no commentary.

### Candidate Resume (parsed JSON):
{json.dumps(resume_data.model_dump(), indent=2)}

### Job Description (parsed JSON):
{json.dumps(jd_data.model_dump(), indent=2)}

### Predefined Evaluation Criteria (Total: 100 Points)
1. Must-Have Skills (40 Points):
   - Calculate the percentage of JD must-have skills found in the resume.
     Multiply that percentage by 40.
2. Relevant Experience (30 Points):
   - If candidate's total_years is null or 0, award 0 points.
   - Award 30 points if the candidate meets or exceeds the minimum required years
     (or if the JD specifies no minimum).
   - If they have less experience, pro-rate the score
     (e.g., 2 years out of 4 required = 15 points).
3. Good-to-Have Skills (20 Points):
   - Calculate the percentage of JD good-to-have skills found.
     Multiply that percentage by 20.
4. Qualifications & Domain (Maximum 10 Points):
   - Award 10 points if they have at least one exact degree/qualification match.
   - Award 5 points if their best match is a somewhat related field.
   - Award 5 points if they have a relevant certificate that comes under qualifications.
   - Award 0 points if completely unrelated and lacking relevant certificates.

### Instructions:
1. Compare candidate's skills with JD must-have and good-to-have skills.
2. Systematically calculate the score for each of the 4 criteria.
3. Sum the scores to get a total out of 100.
4. Convert the total to a 0.0–10.0 scale (e.g., 85 points = 8.5 final match_score).
5. Output reasoning in 2–4 short bullet points.

### Output Format (STRICT JSON):
{{
  "score_breakdown": {{
    "must_have_skills_score": 32.0,
    "experience_score": 30.0,
    "good_to_have_skills_score": 15.0,
    "qualifications_score": 10.0
  }},
  "match_score": 8.7,
  "reasoning": ["point 1", "point 2", "point 3"],
  "matched_skills": {{
    "must_have": ["..."],
    "good_to_have": ["..."]
  }},
  "missing_skills": {{
    "must_have": ["..."],
    "good_to_have": ["..."]
  }},
  "qualification_match": true,
  "experience_match": true
}}
"""

job_fit_matcher = JobFitMatcher()
