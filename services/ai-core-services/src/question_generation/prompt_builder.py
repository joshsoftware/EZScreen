import json
from src.parsing.schemas import ParsedResumeData, ParsedJDData


class QuestionPromptBuilder:
    """Builds the LLM prompt for generating tailored interview questions.

    Injects parsed JD, parsed resume, skill-specific experience, and the full
    match analysis JSON into the question generation prompt template defined
    in AI_PROCESSING.md §5.2.
    """

    def build(self, parsed_jd: ParsedJDData, parsed_resume: ParsedResumeData, match_result: dict) -> str:
        """Construct the question generation prompt with all candidate and JD context injected."""

        # Extract JD fields
        title = parsed_jd.title or "Unknown Role"
        company = parsed_jd.company or "Unknown Company"
        experience_required = json.dumps(parsed_jd.experience_required.model_dump())
        must_have_skills = json.dumps([s.model_dump() for s in parsed_jd.skills.must_have])
        good_to_have_skills = json.dumps([s.model_dump() for s in parsed_jd.skills.good_to_have])
        responsibilities = json.dumps(parsed_jd.responsibilities)
        min_y = parsed_jd.experience_required.min_years or 0

        # Extract candidate fields
        years = parsed_resume.experience.total_years or 0
        domain = json.dumps(parsed_resume.domain_expertise)
        skill_experience_json = json.dumps(
            [se.model_dump() for se in parsed_resume.skill_experience], indent=2
        )

        # Full match JSON
        match_json = json.dumps(match_result, indent=2)

        return f"""You are an expert technical AI preparing questions for an AUTOMATED VIDEO SCREENING interview. The candidate will be recording 1-2 minute video answers. The goal of this round is only to verify whether the candidate genuinely knows the required skills — not to run a full-depth technical L1/L2 interview.

═══ JOB CONTEXT ═══
Role: {title} at {company}
JD Required Experience: {experience_required}
JD Must-Have Skills: {must_have_skills}
JD Good-to-Have Skills: {good_to_have_skills}
JD Responsibilities: {responsibilities}

═══ CANDIDATE CONTEXT ═══
Total Years of Experience: {years}
Candidate Domain Expertise: {domain}

═══ CANDIDATE SKILL-SPECIFIC EXPERIENCE ═══
The following shows the candidate's actual years of hands-on experience for each skill they claim. Use this to calibrate question difficulty per skill.
{skill_experience_json}

═══ FULL MATCH ANALYSIS JSON — use this to decide question focus ═══
{match_json}

How to use the match analysis above:
- matched_skills.must_have      → candidate HAS these → generate depth-verification questions
- missing_skills.must_have      → candidate MISSING these → generate basic awareness questions
- score_breakdown.must_have_skills_score  → if low (< 20/40), add more "lacking_skill" questions
- score_breakdown.good_to_have_skills_score → if 0, ask only basic "what is X" awareness
- reasoning                     → use the overall summary to frame the general tone of questions
- strengths                     → use these verified strengths to frame harder, depth-verification questions
- concerns                      → use these identified gaps or missing skills to frame targeted awareness or behavioral questions
- experience_match: false       → frame experience_domain questions as awareness checks
- qualification_match: false    → do not expect academic-level depth in answers

═══ SCREENING DIFFICULTY RULES ═══
Apply the following difficulty guidance based on the JD requiring {min_y} years of experience:
- If 0-2 years (EASY): Ask basic knowledge-verification questions only.
- If 3-5 years (MEDIUM): Ask single-concept questions that verify genuine hands-on knowledge.
- If 5+ years (HARD): Ask high-level "when to use what" questions.

CRITICAL: When generating a question about a specific skill, check the candidate's skill_experience for that skill's years. A candidate may have 10 total years but only 1 year of Docker — ask Docker questions at "aware" level, not "full_depth".

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

Assign depth dynamically based on the candidate's SKILL-SPECIFIC experience (not just total years) AND the question category:
- Use "aware" for "lacking_skill" and "good_to_have" categories, OR if the candidate has < 2 years experience with that specific skill.
- Use "partial_depth" for "must_have_matched" questions when the candidate has 2-4 years experience with that specific skill, OR if experience_match is false.
- Use "full_depth" for "must_have_matched" and "experience_domain" questions only when the candidate has 5+ years experience with that specific skill and clearly possesses it.

═══ OUTPUT FORMAT ═══
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
