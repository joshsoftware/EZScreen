import json
from src.parsing.schemas import ParsedJDData


class QuestionPromptBuilder:
    """Builds the LLM prompt for generating tailored interview questions.

    Injects parsed JD, parsed resume, skill-specific experience, and the full
    match analysis JSON into the question generation prompt template defined
    in AI_PROCESSING.md §5.2.
    """

    def build(self, parsed_jd: ParsedJDData, match_result: dict) -> str:
        """Construct the question generation prompt with JD and match context injected."""

        # Extract JD fields
        title = parsed_jd.title or "Unknown Role"
        company = parsed_jd.company or "Unknown Company"
        experience_required = json.dumps(parsed_jd.experience_required.model_dump())
        must_have_skills = json.dumps([s.model_dump() for s in parsed_jd.skills.must_have])
        good_to_have_skills = json.dumps([s.model_dump() for s in parsed_jd.skills.good_to_have])
        responsibilities = json.dumps(parsed_jd.responsibilities)
        min_y = parsed_jd.experience_required.min_years or 0


        # Full match JSON
        match_json = json.dumps(match_result, indent=2)

        return f"""You are an expert technical AI preparing tailored interview questions for a candidate.

═══ JOB CONTEXT ═══
Role: {title} at {company}
JD Required Experience: {experience_required}
JD Must-Have Skills: {must_have_skills}
JD Good-to-Have Skills: {good_to_have_skills}
JD Responsibilities: {responsibilities}

═══ FULL MATCH ANALYSIS JSON — use this to decide question focus ═══
{match_json}

How to use the match analysis above:
- matched_skills.must_have      → candidate HAS these → frame questions assuming hands-on experience.
- missing_skills.must_have      → candidate MISSING these → frame questions acknowledging they haven't used it directly.
- reasoning                     → use the overall summary to frame the general tone of questions.
- strengths                     → use these verified strengths to frame harder, depth-verification questions.
- concerns                      → use these identified gaps or missing skills to frame targeted awareness or behavioral questions.

═══ SCREENING DIFFICULTY RULES ═══
CRITICAL: The difficulty of each question MUST be determined on a per-skill basis according to the Job Description's required experience, NOT the candidate's actual experience.
To determine the target experience level for a specific skill question, use the JD's required years of experience for that skill.
- Target Experience Level = jd_required_skill_years (If not explicitly stated in JD, default to the JD's overall min_years).

Example 1: Candidate has 10 years of Java, JD requires 3 years -> Ask a 3-year level question.
Example 2: Candidate has 1 year of Java, JD requires 3 years -> Ask a 3-year level question.

Apply the following difficulty guidance based on the Target Experience Level:
- If 0-2 years (EASY): Ask basic knowledge-verification questions only.
- If 3-5 years (MEDIUM): Ask single-concept questions that verify genuine hands-on knowledge.
- If 5+ years (HARD): Ask high-level "when to use what" or architecture questions.

Generate EXACTLY 15 questions in total across the following categories:
1. CATEGORY "must_have_matched" — from matched_skills.must_have (7–8 questions)
2. CATEGORY "lacking_skill" — from missing_skills.must_have (3–4 questions)
3. CATEGORY "good_to_have" — from JD good-to-have skills (2–3 questions)
4. CATEGORY "experience_domain" — from JD responsibilities (~2 purely technical questions)

═══ ANSWER DEPTH LEVELS ═══
Each question must include an `answer_depth` level ("aware", "partial_depth", or "full_depth") based on how strictly the answer should be evaluated:
- "aware" → awareness only: any reasonable attempt at a response is acceptable.
- "partial_depth" → partial coverage: the answer must touch some of the expected keywords with a basic explanation.
- "full_depth" → full depth: the answer must cover most expected keywords with a clear, accurate explanation.

Assign depth dynamically based ONLY on the JD's REQUIRED EXPERIENCE for that specific skill (Target Experience Level), regardless of whether the candidate possesses the skill or not:
- Use "aware" if the Target Experience Level is < 2 years.
- Use "partial_depth" if the Target Experience Level is 2-4 years.
- Use "full_depth" if the Target Experience Level is 5+ years.

═══ OUTPUT FORMAT ═══i
Return a JSON array only. No markdown, no commentary.
[
  {{
    "id": 1,
    "category": "must_have_matched | lacking_skill | good_to_have | experience_domain",
    "skill_focus": "the specific skill or topic",
    "question": "the interview question",
    "expected_keywords": ["3 to 5 keywords a correct answer must touch"],
    "answer_depth": "aware | partial_depth | full_depth"
  }}
]
"""


question_prompt_builder = QuestionPromptBuilder()
