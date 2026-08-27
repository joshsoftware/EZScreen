import asyncio
import json
import datetime
import calendar
from src.core.storage import storage_client
from src.parsing.docling_wrapper import docling_wrapper
from src.llm.client import OllamaClient
from src.core.logger import logger

# Restrict OCR to a single concurrent thread to prevent PyTorch OpenMP thread deadlocks,
# while still offloading it to a background thread so the FastAPI event loop is NOT blocked!
# Restrict to 1 concurrent OCR extraction to prevent PyTorch CPU thread deadlocks
ocr_semaphore = asyncio.Semaphore(1)

class ResumeParser:
    def __init__(self):
        self.llm_client = OllamaClient()

    async def parse_s3_file(self, s3_key: str) -> dict:
        """Downloads from S3, extracts markdown, and parses using LLM."""
        # 1. Download file (Non-blocking)
        tmp_path = await asyncio.to_thread(storage_client.download_to_tempfile, s3_key)
        
        try:
            # 2. Extract Text (Sequential to prevent PyTorch thread deadlocks, but non-blocking for FastAPI)
            async with ocr_semaphore:
                markdown_text = await asyncio.to_thread(docling_wrapper.extract_markdown, tmp_path)
            
            # 3. Build Prompt
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            prompt = self._build_prompt(markdown_text, current_date)
            
            # 4. Call LLM (using the OpenAI chat endpoint to strictly enforce JSON)
            logger.info("Sending resume extraction prompt to LLM")
            response = await self.llm_client.openai_chat_generate(prompt=prompt, temperature=0.1, timeout=120.0)
            
            # 5. Parse JSON Response
            raw_json = response.response.strip()
            try:
                # Basic cleanup in case LLM wraps it in markdown blocks
                if raw_json.startswith("```json"):
                    raw_json = raw_json[7:]
                if raw_json.startswith("```"):
                    raw_json = raw_json[3:]
                if raw_json.endswith("```"):
                    raw_json = raw_json[:-3]
                    
                parsed_data = json.loads(raw_json.strip())
                if "parsed_resume" in parsed_data:
                    parsed_data = parsed_data["parsed_resume"]
                    
                self._recalculate_experience(parsed_data)
                return parsed_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON output: {e}\nRaw Output: {response.response}")
                raise ValueError("LLM returned invalid JSON")
                
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _recalculate_experience(self, parsed_data: dict) -> None:
        """Overrides the LLM's hallucinated date math with strict Python datetime calculations."""
        if not parsed_data or "experience" not in parsed_data:
            return
        
        roles = parsed_data["experience"].get("roles", [])
        if not roles:
            return
            
        def parse_date(date_str, is_end_date=False):
            if not date_str or str(date_str).lower() in ("present", "current", "now", "null", "none"):
                return datetime.datetime.now()
            date_str = str(date_str).strip()
            try:
                if len(date_str) == 10:
                    return datetime.datetime.strptime(date_str, "%Y-%m-%d")
                elif len(date_str) == 7:
                    dt = datetime.datetime.strptime(date_str, "%Y-%m")
                    if is_end_date:
                        _, last_day = calendar.monthrange(dt.year, dt.month)
                        dt = dt.replace(day=last_day)
                    return dt
                elif len(date_str) == 4:
                    dt = datetime.datetime.strptime(date_str, "%Y")
                    if is_end_date:
                        dt = dt.replace(month=12, day=31)
                    return dt
            except ValueError:
                pass
            return None

        intervals = []
        for role in roles:
            start_dt = parse_date(role.get("start_date"), is_end_date=False)
            end_dt = parse_date(role.get("end_date"), is_end_date=True)
            
            if start_dt and end_dt and start_dt <= end_dt:
                days = (end_dt - start_dt).days
                role["years"] = round(days / 365.25, 1)
                intervals.append([start_dt, end_dt])
            else:
                role["years"] = 0.0
                
        # Merge overlapping intervals for total_years
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

    def _build_prompt(self, markdown_text: str, current_date: str) -> str:
        return f"""
You are an expert resume parser specializing in technology and business resumes. Extract ONLY information explicitly stated in the provided resume and return exactly one valid JSON object matching the schema below.

CURRENT DATE: {current_date}
Use this date as the reference date for all duration calculations involving "present". Do not use any other assumed current date.

GENERAL RULES:

* Output ONLY valid JSON. No markdown, explanations, comments, or extra text.
* Never guess, infer, fabricate, or fill missing information using common knowledge.
* If information is not explicitly available, use null for scalar fields and [] for arrays.
* Extract information from the entire resume, including the header, summary, skills, experience, projects, education, and certifications.
* Normalize and deduplicate equivalent skills while preserving their meaning.
* Do not infer a skill, technology, responsibility, industry, or achievement from a job title alone.

OUTPUT FORMAT:

* primary_skills MUST always be an array of strings, even if there is only one skill.
* secondary_skills MUST always be an array of strings, even if there is only one skill.
* domain_expertise MUST always be an array of strings, even if there is only one domain.
* roles MUST always be an array of objects, with one object per distinct work experience role.
* highlights MUST always be an array of strings for every role, even if there is only one highlight.
* education_certificates MUST always be an array of objects, even if there is only one degree or certification.
* Never return an array field as a single string, object, or null.
* If no information is available for an array field, return [].
* Do not omit any field defined in the schema.

SKILLS:

* primary_skills: Core technical/hard skills explicitly mentioned, including programming languages, frameworks, libraries, databases, cloud platforms, DevOps, infrastructure, APIs, testing, data technologies, and other technical tools.
* secondary_skills: Supporting technologies, tools, methodologies, soft skills, leadership skills, and less-central technical skills explicitly mentioned.
* domain_expertise: Explicitly stated industries or business domains, such as Finance, Banking, Healthcare, E-commerce, Logistics, Retail, SaaS, or Telecom.
* Do not place the same normalized skill in both primary_skills and secondary_skills.
* Do not infer skills from projects or job titles unless the skill is explicitly stated.
* Normalize obvious naming variations, e.g. "React.js"/"ReactJS" → "React", "Postgres"/"PostgreSQL" → "PostgreSQL".
* CRITICAL RULE: Completely ignore Internship roles. Do not extract any skills from internship descriptions into primary_skills or secondary_skills.

SKILL-SPECIFIC EXPERIENCE (skill_experience):

* For EVERY skill identified in primary_skills and secondary_skills, determine the candidate's total years of experience with that specific skill.
* STEP 1 - Calculate from ROLE HIGHLIGHTS for ALL skills:
  - Look at each role in the "Professional Experience" / "Work Experience" section.
  - A skill is considered "used in a role" ONLY if it is explicitly mentioned in that role's bullet points/highlights.
  - Sum the durations (years) of all roles where the skill is explicitly mentioned.
  - Subtract overlapping role durations to prevent double-counting.
  - This provides the `calculated_role_years`.
* STEP 2 - Check for DIRECT per-skill year statements:
  - A valid explicit statement is when the candidate directly associates a specific number of years with one or more specific skills, such as: "Java (5 years)", "7+ years of Python", or "10 years of experience in Java, Spring".
  - If a candidate includes a broad professional summary statement like "3+ years of experience in enterprise development using Java, Spring Boot", apply that exact number of years (e.g., 3.0) to EACH of the skills listed.
  - CRITICAL: If a candidate states a number of years in a professional summary paragraph (e.g., "7 years of success in DevOps..."), and then lists skills within that SAME summary paragraph (e.g., "... Skilled in Jenkins, Docker"), you MUST apply that exact number of years (e.g., 7.0) to ALL skills mentioned anywhere within that summary block, even if they are in separate sentences.
  - This provides the `stated_years`.
* STEP 3 - Determine Final Skill Experience:
  - If a skill has both `stated_years` and `calculated_role_years`, you MUST use the MAXIMUM of the two values. (e.g., if summary says 3 years, but roles add up to 4.5 years, use 4.5 years).
  - If a skill only has one of the values, use that value.
* Round the final skill experience to 1 decimal place.
* If a skill appears ONLY in a "Technical Skills" section or summary but is NOT mentioned in any role highlight or project, assign it 0.0 years.

WORK EXPERIENCE:

* Extract every distinct professional role separately.
* CRITICAL RULE - INTERNSHIPS: If a role title or description contains the word "Intern" or "Internship", you MUST skip it entirely. DO NOT extract it. DO NOT add its duration to `total_years`. DO NOT add its duration to any skill. Treat the internship as if it does not exist.
* For every role, extract title, company, start_date, end_date, years, and highlights.
* Extract dates only from information explicitly associated with that role.
* If a date is unavailable, use null. Never infer a missing date from another role.
* If the role is explicitly ongoing/current, end_date must be "present".
* Date format:
  * YYYY-MM-DD when exact date is explicitly available.
  * YYYY-MM when month and year are explicitly available.
  * YYYY when only the year is explicitly available.
* Calculate years from the extracted start_date and end_date.
* If both month and year are available, calculate the exact elapsed duration using those months.
* If only years are available, calculate duration using the difference between the years. For example, 2022–2024 = 2.00 years.
* If only a start year is available and the role is ongoing, calculate from January 1 of that year through CURRENT DATE.
* If start month/year is available and the role is ongoing, calculate from the first day of that month through CURRENT DATE.
* If an end month/year is available, calculate through the end of that month.
* If an exact day is available, use the exact day.
* Calculate years as elapsed days / 365.25 when exact or month-level dates are available, and round to 1 decimal place.
* For year-only ranges, use the year difference directly and round to 1 decimal place.
* Do not return years as null merely because only a year or month/year is available.
* Return years as null only when the available dates are genuinely insufficient to calculate a reliable duration.
* total_years must represent unique professional experience across all extracted roles. Overlapping employment periods must not be double-counted.
* CRITICAL RULE FOR MATH: Inside the `experience` object, you MUST first provide a string field called `total_years_calculation`. In this field, you must write out the exact mathematical addition of the individual role `years` (e.g., "7.5 + 0.6 = 8.1"). Subtract any overlapping durations.
* After `total_years_calculation`, provide `total_years` as the final calculated float exactly matching your calculation. Do not guess.
* `total_years` and individual role `years` should be rounded and formatted to only 1 decimal place (e.g., 3.45 becomes 3.4).

ROLE HIGHLIGHTS:

* highlights must contain concise, factual information specifically associated with that role.
* Include role-specific technologies explicitly mentioned in that role, including programming languages, frameworks, libraries, databases, cloud, DevOps, CI/CD, APIs, monitoring, infrastructure, testing, and data tools.
* Include important responsibilities, projects, architectures, systems, and measurable achievements explicitly stated for that role.
* Preserve technology + context. For example: "Developed microservices using Java and Spring Boot" rather than only "Java".
* A technology may appear in both global skills and the relevant role's highlights.
* Associate a technology with a role ONLY when the resume explicitly connects it to that role's work, project, responsibility, or description.
* Do not copy technologies from another role into the current role.
* Do not copy the entire global skills section into every role.
* Do not infer technologies from the job title. For example, "DevOps Engineer" does not automatically mean AWS, Docker, Kubernetes, or Jenkins.
* Keep highlights concise and information-dense.
* If no role-specific details are available, return [].

PERSONAL INFORMATION:

* Extract first_name, last_name, phone_number, email, linkedin_url, github_url, and leetcode_url only when explicitly present.
* Do not expand initials into full names.
* Do not infer missing contact information.
* Preserve explicitly provided contact information accurately.

NAME PARSING:

* Extract first_name and last_name based on the person's actual given name and family/surname, not simply by word position.
* Do not assume the first word is the first name or that the last word is the last name.
* If the resume does not provide enough reliable information to determine the first name and last name, use null rather than guessing.

EDUCATION AND CERTIFICATIONS:

* Extract every explicitly stated degree and certification.
* type must be exactly "degree" or "certification".
* name must contain the explicitly stated degree or certification name.
* issuer must contain the explicitly stated university, institution, or certification issuer when available.
* year must contain the explicitly stated graduation, completion, or certification year when available.
* Never infer an issuer or year.

FINAL VALIDATION:

Before returning the JSON, verify that:

* Every schema field is present, even when its value is null or [].
* Every extracted role has a title, company, start_date, end_date, years, and highlights field.
* Ongoing roles use "present" as end_date.
* Calculated years are numeric or null, never strings.
* primary_skills, secondary_skills, domain_expertise, roles, highlights, and education_certificates are always arrays as defined in the schema.
* Empty array fields contain [] rather than null.
* Skills are deduplicated and normalized.
* Role highlights contain only information associated with that role.
* No technology was inferred solely from a job title.
* No missing information was guessed.
* The output exactly matches the provided schema.
* The output is valid JSON.

SCHEMA:
""" + """
{
"parsed_resume": {
"personal_info": {
"first_name": "string or null",
"last_name": "string or null",
"phone_number": "string or null",
"email": "string or null",
"linkedin_url": "string or null",
"github_url": "string or null",
"leetcode_url": "string or null"
},
"primary_skills": ["string"],
"secondary_skills": ["string"],
"domain_expertise": ["string"],
"experience": {
"total_years_calculation": "string",
"total_years": "number or null",
"roles": [
{
"title": "string or null",
"company": "string or null",
"start_date": "string or null",
"end_date": "string or null",
"years": "number or null",
"highlights": ["string"]
}
]
},
"skill_experience": [
{
"skill": "string",
"years": "number or null"
}
],
"education_certificates": [
{
"name": "string",
"issuer": "string or null",
"year": "string or null",
"type": "degree or certification"
}
]
}
}
""" + f"""
RESUME TEXT:
{markdown_text}
"""

resume_parser = ResumeParser()
