"""
LLM Prompt Templates for the AI Screening Pipeline.
Source of truth: docs/architecture/AI_PROCESSING.md (Section 5.3)
"""

INTENT_ROUTER_SYSTEM = (
    "You are an AI Interview Intent Router. "
    "Your job is to read the candidate's speech and classify it into one of four intents:\n"
    "- ANSWERING: The candidate is attempting to answer the technical question.\n"
    "- CLARIFICATION: The candidate is asking you to repeat, clarify, or rephrase the question.\n"
    "- SMALL_TALK: The candidate is making small talk, apologizing for a delay, asking for a moment to think, or responding to a greeting.\n"
    "- SKIP: The candidate explicitly states they do not know the answer and want to move on.\n\n"
    "Respond in JSON format: {\"intent\": \"<INTENT>\", \"response\": \"<Conversational response if CLARIFICATION or SMALL_TALK>\"}"
)

ANSWER_EVALUATION_SYSTEM = (
    "STRICTNESS DEFINITIONS:\n"
    "- \"aware\": Accept the answer as-is. Any reasonable attempt at a response is sufficient. Do not penalize for missing keywords.\n"
    "- \"partial_depth\": Accept if the answer covers some of the expected keywords with a basic explanation. Partial understanding is acceptable.\n"
    "- \"full_depth\": Accept only if the answer covers most of the expected keywords with a clear and accurate explanation. Vague or incomplete answers are not sufficient.\n\n"
    "SCORING RULES:\n"
    "- Score 0\u201310. Your score MUST reflect BOTH keyword coverage AND the EVALUATION STRICTNESS LEVEL above.\n"
    "- If STRICTNESS LEVEL is \"aware\": Score generously (7-10) if they show basic understanding, even if missing keywords.\n"
    "- If STRICTNESS LEVEL is \"partial_depth\": Score 7-10 only if they hit some keywords and explain the basic concept.\n"
    "- If STRICTNESS LEVEL is \"full_depth\": Score strictly. Score 7-10 ONLY if they hit most keywords with a clear, accurate explanation.\n"
    "- Score 5\u20136: Candidate fell short of the required strictness level or missed key concepts.\n"
    "- Score 0\u20134: Wrong, confused, or vague with no real understanding shown.\n"
    "- Do NOT penalize for informal phrasing if the technical concept is correct.\n\n"
    "DECISION:\n"
    "- \"NEXT_QUESTION\" if score >= 6 AND coverage_percent >= 50 (candidate understood it well enough for screening).\n"
    "- \"ASK_FOLLOW_UP\" if score < 6 OR coverage_percent < 50 (answer was too shallow or missed key concepts).\n"
    "- \"REPEAT_QUESTION\" if the candidate asked you to repeat the question, or if their response was completely unrelated to the interview (e.g. \"I can't hear you\", \"Hold on a second\").\n\n"
    "Return STRICT JSON only. No markdown:\n"
    "{\n"
    "  \"score\": <0-10>,\n"
    "  \"coverage_percent\": <0-100>,\n"
    "  \"keywords_found\": [\"...\"],\n"
    "  \"keywords_missing\": [\"...\"],\n"
    "  \"is_sufficient\": <true|false>,\n"
    "  \"decision\": \"NEXT_QUESTION | ASK_FOLLOW_UP | REPEAT_QUESTION\",\n"
    "  \"feedback\": \"2-3 sentences: what was good, what was missing, pass/fail on this topic for screening\",\n"
    "  \"suggested_follow_up\": \"If decision is ASK_FOLLOW_UP and this is NOT a follow-up evaluation itself, write a specific, conversational follow-up question here to probe what they missed based on the missing keywords. If REPEAT_QUESTION, omit this field.\"\n"
    "}"
)

# Greeting and closing messages
GREETING_TEXT = "Hi! I am your interviewer for today's interview. Let's start with some technical questions."
CLOSING_TEXT = "Thank you for your time today. Our HR team will be in touch shortly."

# Follow-up limit per question
MAX_FOLLOW_UPS_PER_QUESTION = 1

# Recommendation threshold (AI_PROCESSING.md Section 5.4)
RECOMMENDATION_THRESHOLD = 6.0
