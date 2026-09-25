"""
LLM Prompt Templates for the AI Screening Pipeline.
Source of truth: docs/architecture/AI_PROCESSING.md (Section 5.3)
"""

from src.core.config import settings

# A balanced final answer score (0-10) below this asks a follow-up; at or above
# it moves to the next question. Used by both the LLM prompt and AnswerEvaluator.
FOLLOW_UP_SCORE_THRESHOLD = 4

UNIFIED_SCREENING_SYSTEM = (
    "You are an AI Screening Interview turn processor. For every candidate utterance, "
    "first classify intent, then \u2014 only if the candidate is answering \u2014 evaluate the answer.\n\n"
    "STEP 1 \u2014 INTENT (always classify exactly one):\n"
    "- ANSWERING: The candidate is attempting to answer the technical question. (Even if their answer is completely wrong, confusing, or poorly transcribed, if they are using technical terms or trying to answer, choose this!).\n"
    "- CLARIFICATION: The candidate is asking you to repeat, clarify, or rephrase the question.\n"
    "- SMALL_TALK: The candidate is ONLY asking for a moment to think (e.g. 'give me a second'), apologizing for a delay, confirming they are present (e.g. 'Yes I am here'), or responding to a greeting/closing. DO NOT use this for rambling. If classified as SMALL_TALK, provide a polite conversational response that encourages them or repeats the question to get them back on track.\n"
    "- SKIP: The candidate explicitly states they do not know the answer and want to move on.\n\n"
    "STEP 2 \u2014 RESPONSE (conditional):\n"
    "- If intent is CLARIFICATION or SMALL_TALK: set \"response\" to a polite, brief conversational reply (per the STEP 1 guidance above).\n"
    "- Otherwise: set \"response\" to \"\".\n\n"
    "STEP 3 \u2014 EVALUATION (only if intent is ANSWERING; omit all evaluation fields for every other intent):\n\n"
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
    "- KEYWORD MATCH SCORE (50%): You judge how many of the EXPECTED KEYWORDS the candidate actually covered and return it as \"keyword_match_score\" on a 0-10 scale (10 x covered keywords / total expected keywords, rounded to one decimal). Also list the covered ones in \"keywords_found\" and the rest in \"keywords_missing\".\n"
    "KEYWORD MATCHING RULES (apply to \"keyword_match_score\", \"keywords_found\" and \"keywords_missing\"):\n"
    "- Judge each expected keyword by meaning, not exact wording. Count it as covered when the candidate clearly demonstrates that concept: exact term, plural/tense variant, spacing or casing variant (e.g. \"hashmap\" for \"HashMap\"), common alias or abbreviation (e.g. \"k8s\" for \"Kubernetes\"), or an accurate paraphrase or description of it.\n"
    "- The candidate speech is a speech-to-text transcript. Treat obvious mis-transcriptions of a keyword (e.g. \"cooper netties\" for \"Kubernetes\") as covered when the surrounding context makes the intended term clear.\n"
    "- Do NOT count a keyword that is only echoed from the question, denied or negated (e.g. \"I don't know Docker\", \"it is not related to Docker\"), or used incorrectly or in a contradictory way.\n"
    "- Use only the candidate's own words. Do not count keywords that appear only in the interviewer's (AI) lines.\n"
    "- \"keywords_found\" and \"keywords_missing\" must together contain each expected keyword exactly once, copied exactly from the EXPECTED KEYWORDS list. Never invent, rename, or add keywords. \"keyword_match_score\" must be consistent with those lists.\n"
    "- Keyword matching is independent of strictness: do not require deeper explanation for a keyword to count.\n"
    "- ANSWER QUALITY SCORE (50%): Independently assess conceptual correctness, relevance, clarity, explanation depth, and the EVALUATION STRICTNESS LEVEL. Do not penalize informal phrasing when the technical concept is correct.\n"
    "- Evaluate the candidate's actual answer against the current interview question; do not score an answer that was not given.\n"
    "- The application computes the FINAL score and validates the final decision from your keyword_match_score and answer_quality_score. Supply both, independently.\n"
    "- FINAL score = round((keyword_match_score + answer_quality_score) / 2) to the nearest whole number. Never let one component outweigh the other.\n"
    "- Apply \"aware\" generously to the ANSWER QUALITY SCORE when the candidate shows basic understanding; apply \"partial_depth\" and \"full_depth\" according to the required explanation depth and accuracy.\n"
    f"- Score 0\u2013{FOLLOW_UP_SCORE_THRESHOLD - 1}: The balanced final score means the answer is wrong, confused, vague, or has little meaningful understanding. "
    f"Score {FOLLOW_UP_SCORE_THRESHOLD}\u20136: It shows partial understanding but material gaps.\n\n"
    "DECISION:\n"
    f"- \"NEXT_QUESTION\" if the balanced final score >= {FOLLOW_UP_SCORE_THRESHOLD} (candidate understood it well enough for screening).\n"
    f"- \"ASK_FOLLOW_UP\" if the balanced final score < {FOLLOW_UP_SCORE_THRESHOLD} (answer was too shallow or missed key concepts).\n"
    "- \"REPEAT_QUESTION\" if the candidate asked you to repeat the question, or if their response was completely unrelated to the interview (e.g. \"I can't hear you\", \"Hold on a second\").\n\n"
    "Return STRICT JSON only. No markdown:\n"
    "{\n"
    "  \"intent\": \"ANSWERING | CLARIFICATION | SMALL_TALK | SKIP\",\n"
    "  \"response\": \"<required for CLARIFICATION or SMALL_TALK per STEP 2; empty string otherwise>\",\n"
    "  \"keyword_match_score\": <0-10; required only when intent is ANSWERING>,\n"
    "  \"keywords_found\": [\"<expected keyword covered, copied exactly from EXPECTED KEYWORDS>\"] (required only when intent is ANSWERING; [] if none),\n"
    "  \"keywords_missing\": [\"<expected keyword not covered>\"] (required only when intent is ANSWERING; [] if none),\n"
    "  \"answer_quality_score\": <0-10; required only when intent is ANSWERING>,\n"
    "  \"decision\": \"NEXT_QUESTION | ASK_FOLLOW_UP | REPEAT_QUESTION; required only when intent is ANSWERING\",\n"
    "  \"feedback\": \"2-3 sentences: what was good, what was missing, pass/fail on this topic for screening; required only when intent is ANSWERING\",\n"
    "  \"suggested_follow_up\": \"If intent is ANSWERING and decision is ASK_FOLLOW_UP and this is NOT a follow-up evaluation itself, write one specific, conversational follow-up question that addresses the weakest keyword or answer-quality gap. If REPEAT_QUESTION or not ANSWERING, omit this field.\"\n"
    "}"
)

# Greeting and closing messages
GREETING_TEXT = "Hi! I am your interviewer for today's interview. We’ll begin with a few technical questions. Let me know when you’re ready."
CLOSING_TEXT = "Thank you for your time today. Our HR team will be in touch shortly."
SILENCE_PROMPT_TEXT = "Are you there?"
# Spoken after every completed question (except REPEAT_QUESTION). Named as a
# constant, not an inline literal, so the TTS warm cache (see
# PipecatInterviewPolicy._warm_tts_cache) pre-synthesizes the exact same string.
ANSWER_ACKNOWLEDGEMENT_TEXT = "Thank you for answering the question."
# Spoken as its own utterance, immediately followed by a second speak() of
# the question text itself — never concatenated into one string. Keeping
# them separate means the question half is spoken verbatim and hits the TTS
# cache (it was pre-warmed as-is); "Let me repeat the question: <question>"
# as a single string never would, since the cache is keyed on exact text.
REPEAT_QUESTION_PREFIX_TEXT = "Let me repeat the question."
REPEAT_QUESTION_LIMIT_TEXT = (
    "I have already repeated the question once. "
    "Please share your best answer when you are ready."
)
SILENCE_PROMPT_SECONDS = 30
# Prompt twice at 30-second intervals, then close after the final 30-second
# unanswered interval (90 seconds total).
MAX_SILENCE_PROMPTS = 2
# A candidate may pause briefly between clauses.  A final STT segment is held
# for this short period so a continuation is evaluated as one answer.
# Env-overridable via SCREENING_ANSWER_SETTLE_SECONDS (default 2.0s). See
# docs/architecture/SCREENING_BOT_LATENCY_OPTIMIZATION.md Phase 2 for the tuning
# rationale and hard floor (1.5s).
ANSWER_SETTLE_SECONDS = settings.screening_answer_settle_seconds
# This is intentionally separate from SILENCE_PROMPT_SECONDS: the closing
# reply window must never speak the inactivity prompt.
CLOSING_REPLY_TIMEOUT_SECONDS = 30

# Follow-up limit per question
MAX_FOLLOW_UPS_PER_QUESTION = 1

# Spoken while waiting on a slow LLM turn (classify_and_evaluate), so a
# multi-second gap doesn't read as dead air. Named constants (not inline
# literals) so the TTS warm cache pre-synthesizes the exact same strings —
# see PipecatInterviewPolicy._run_filler_schedule and tts_prewarm.known_bot_texts.
FILLER_TEXTS = [
    "Alright, one moment.",
    "Just a moment, please.",
    "Okay, give me a second.",
]
# Absolute seconds after the candidate stopped talking at which each
# successive filler should fire — not gaps between them (see
# PipecatInterviewPolicy._run_filler_schedule, which measures from
# handle_candidate_speech_stopped, not from when the LLM call happens to
# start, and can fire *during* the ANSWER_SETTLE_SECONDS wait, not only after
# it — a candidate resuming speech mid-settle already gets the same
# InterruptionFrame barge-in as any other bot utterance, so there's no
# safety reason to hold the first filler back until settle ends). Loosens up
# over time so a quick early reassurance doesn't turn into a repetitive,
# noticeable beat on a genuinely long wait. The task is cancelled (see
# _cancel_filler_schedule) the instant classify_and_evaluate resolves, so a
# filler never overlaps the real response that follows; once this list is
# exhausted with no result yet, the policy just keeps waiting silently.
FILLER_SCHEDULE_SECONDS = [1.5, 4.5, 8.0]

# How often _end_after_inactivity rechecks whether the candidate has stopped
# talking, while they're still mid-answer past SILENCE_PROMPT_SECONDS. A
# named constant (not an inline literal) purely so tests can shrink it.
CANDIDATE_SPEAKING_POLL_SECONDS = 1.0

# Recommendation threshold (AI_PROCESSING.md Section 5.4)
RECOMMENDATION_THRESHOLD = 6.0

FINAL_QUALITATIVE_SUMMARY_PROMPT = (
    "You are an expert technical interviewer summarizing a candidate's performance in a screening interview. "
    "Review the following interview transcript and the mathematically calculated category scores.\n\n"
    "═══ CATEGORY SCORES ═══\n"
    "{category_scores}\n\n"
    "═══ INTERVIEW TRANSCRIPT ═══\n"
    "{transcript}\n\n"
    "Write exactly 5 to 6 bullet points summarizing the candidate's technical depth, strengths, and weaknesses. "
    "CRITICAL REQUIREMENT: You MUST explicitly comment on the candidate's 'command' of the specific categories evaluated "
    "(Must-Have, Domain, Good-To-Have, Lacking) by referencing their numerical scores and concrete technologies from their answers.\n"
    "Example formats:\n"
    "- 'Demonstrated excellent command of Must-Have skills (scored 8.5/10), answering complex Java and Spring Boot questions easily.'\n"
    "- 'Showed adequate command of Domain-specific knowledge (scored 6.0/10) regarding E-commerce architecture.'\n"
    "- 'Lacks command in Good-To-Have skills (scored 3.0/10), specifically struggling with Docker optimization.'\n"
    "Only comment on categories that were actually asked in the transcript. "
    "Ensure the final bullet point provides an overall summary of their fit.\n\n"
    "Return STRICT JSON only. No markdown, no commentary:\n"
    "{{\n"
    "  \"interview_summary\": [\n"
    "    \"bullet point 1\",\n"
    "    \"bullet point 2\",\n"
    "    \"bullet point 3\",\n"
    "    \"bullet point 4\",\n"
    "    \"bullet point 5\"\n"
    "  ]\n"
    "}}"
)
