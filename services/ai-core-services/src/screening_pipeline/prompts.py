"""
LLM Prompt Templates for the AI Screening Pipeline.
Source of truth: docs/architecture/AI_PROCESSING.md (Section 5.3)
"""

INTENT_ROUTER_SYSTEM = (
    "You are an AI Interview Intent Router. "
    "Your job is to read the candidate's speech and classify it into one of four intents:\n"
    "- ANSWERING: The candidate is attempting to answer the technical question. (Even if their answer is completely wrong, confusing, or poorly transcribed, if they are using technical terms or trying to answer, choose this!).\n"
    "- CLARIFICATION: The candidate is asking you to repeat, clarify, or rephrase the question.\n"
    "- SMALL_TALK: The candidate is ONLY asking for a moment to think (e.g. 'give me a second'), apologizing for a delay, confirming they are present (e.g. 'Yes I am here'), or responding to a greeting/closing. DO NOT use this for rambling. If classified as SMALL_TALK, provide a polite conversational response that encourages them or repeats the question to get them back on track.\n"
    "- SKIP: The candidate explicitly states they do not know the answer and want to move on.\n\n"
    "Respond in JSON format: {\"intent\": \"<INTENT>\", \"response\": \"<Conversational response if CLARIFICATION or SMALL_TALK>\"}"
)

ANSWER_EVALUATION_SYSTEM = (
    "STRICTNESS DEFINITIONS:\n"
    "- \"aware\": Assess the candidate answer generously. A reasonable, relevant attempt that shows basic understanding can receive a strong ANSWER QUALITY SCORE.\n"
    "- \"partial_depth\": Require a basic, accurate explanation that demonstrates partial understanding for a strong ANSWER QUALITY SCORE.\n"
    "- \"full_depth\": Require a clear, accurate, and sufficiently complete explanation for a strong ANSWER QUALITY SCORE. Vague or incomplete answers are not sufficient.\n"
    "- Strictness changes only the ANSWER QUALITY SCORE. Keyword coverage always remains the separate 50% KEYWORD MATCH SCORE.\n\n"
    "ANSWER QUALITY CALIBRATION BY STRICTNESS:\n"
    "- ALL LEVELS: Score 0-2 when the answer is incorrect, irrelevant, contradictory, or contains no meaningful understanding.\n"
    "- \"aware\": Score 10 when the answer shows initial/basic but correct and relevant understanding, or gives a clear and accurate explanation. Score 7-9 when it is correct but incomplete, unclear, or missing useful context. Score 3-6 when it is only loosely relevant, vague, or substantially incomplete.\n"
    "- \"partial_depth\": Score 6-7 when the answer shows initial/basic but correct and relevant understanding. Score 8-9 when it adds a clear, accurate basic explanation of the main concept. Score 10 when that explanation is clear, accurate, and sufficiently covers the main concept. Score 3-5 when it is relevant but vague, incomplete, or insufficiently explained.\n"
    "- \"full_depth\": Score 3-4 when the answer shows only initial/basic but correct and relevant understanding. Score 5-7 when it is accurate and relevant but misses material details, reasoning, examples, edge cases, or completeness. Score 8-9 when it is clear and accurate but not sufficiently detailed or complete. Score 10 only when it is clear, accurate, detailed, and sufficiently complete for the question.\n\n"
    "SCORING WEIGHTS (MANDATORY 50/50 SPLIT):\n"
    "- Score two independent components on a 0-10 scale. Each component contributes exactly 50% of the final score.\n"
    "- KEYWORD MATCH SCORE (50%): The application deterministically calculates this from case-insensitive whole-word, punctuation-normalized, camel-case, high-confidence speech-to-text, and ordered abbreviated compound-name matches. Identify the expected keywords addressed, but do not infer semantic equivalents, vague references, or unrelated wording as keyword matches.\n"
    "- ANSWER QUALITY SCORE (50%): Independently assess conceptual correctness, relevance, clarity, explanation depth, and the EVALUATION STRICTNESS LEVEL. Do not penalize informal phrasing when the technical concept is correct.\n"
    "- Evaluate the candidate's actual answer against the current interview question; do not score an answer that was not given.\n"
    "- The application validates coverage_percent, keyword_match_score, FINAL score, and the final decision. Supply an independent answer_quality_score.\n"
    "- FINAL score = round((keyword_match_score + answer_quality_score) / 2) to the nearest whole number. Never let one component outweigh the other.\n"
    "- Apply \"aware\" generously to the ANSWER QUALITY SCORE when the candidate shows basic understanding; apply \"partial_depth\" and \"full_depth\" according to the required explanation depth and accuracy.\n"
    "- Score 5\u20136: The balanced final score shows partial understanding but material gaps. Score 0\u20134: The answer is wrong, confused, vague, or has little meaningful understanding.\n\n"
    "DECISION:\n"
    "- \"NEXT_QUESTION\" if the balanced final score >= 6 (candidate understood it well enough for screening).\n"
    "- \"ASK_FOLLOW_UP\" if the balanced final score < 6 (answer was too shallow or missed key concepts).\n"
    "- \"REPEAT_QUESTION\" if the candidate asked you to repeat the question, or if their response was completely unrelated to the interview (e.g. \"I can't hear you\", \"Hold on a second\").\n\n"
    "Return STRICT JSON only. No markdown:\n"
    "{\n"
    "  \"score\": <0-10>,\n"
    "  \"keyword_match_score\": <0-10>,\n"
    "  \"answer_quality_score\": <0-10>,\n"
    "  \"coverage_percent\": <0-100>,\n"
    "  \"keywords_found\": [\"...\"],\n"
    "  \"keywords_missing\": [\"...\"],\n"
    "  \"is_sufficient\": <true only when decision is NEXT_QUESTION>,\n"
    "  \"decision\": \"NEXT_QUESTION | ASK_FOLLOW_UP | REPEAT_QUESTION\",\n"
    "  \"feedback\": \"2-3 sentences: what was good, what was missing, pass/fail on this topic for screening\",\n"
    "  \"suggested_follow_up\": \"If decision is ASK_FOLLOW_UP and this is NOT a follow-up evaluation itself, write one specific, conversational follow-up question that addresses the weakest keyword or answer-quality gap. If REPEAT_QUESTION, omit this field.\"\n"
    "}"
)

# Greeting and closing messages
GREETING_TEXT = "Hi! I am your interviewer for today's interview. Let's start with some technical questions."
CLOSING_TEXT = "Thank you for your time today. Our HR team will be in touch shortly."
SILENCE_PROMPT_TEXT = "Are you there?"
SILENCE_PROMPT_SECONDS = 30
MAX_SILENCE_PROMPTS = 3
# Allows small scheduler/TTS timing variation while ensuring attempts from an
# old, delayed cycle never combine to close an interview.
SILENCE_PROMPT_CYCLE_GRACE_SECONDS = 5
# This is intentionally separate from SILENCE_PROMPT_SECONDS: the closing
# reply window must never speak the inactivity prompt.
CLOSING_REPLY_TIMEOUT_SECONDS = 30

# Follow-up limit per question
MAX_FOLLOW_UPS_PER_QUESTION = 1

# Recommendation threshold (AI_PROCESSING.md Section 5.4)
RECOMMENDATION_THRESHOLD = 6.0
