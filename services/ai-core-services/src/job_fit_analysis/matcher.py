import json
from typing import Optional

from src.common.llm_utils import parse_llm_json
from src.core.logger import logger
from src.job_fit_analysis.prompt_builder import matching_prompt_builder
from src.job_fit_analysis.score_calculator import recalculate_scores
from src.llm.client import OllamaClient
from src.parsing.schemas import ParsedJDData, ParsedResumeData


class JobFitMatcher:
    """Compares parsed resume against parsed JD using LLM, with deterministic score correction."""

    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm_client = llm_client or OllamaClient()

    async def analyze_fit(self, resume_data: ParsedResumeData, jd_data: ParsedJDData) -> dict:
        """Compares the parsed resume against the parsed JD using LLM."""
        response = None
        try:
            prompt = matching_prompt_builder.build(resume_data, jd_data)

            logger.info("Sending job fit analysis prompt to LLM")
            response = await self.llm_client.openai_chat_generate(
                prompt=prompt, temperature=0.1, timeout=120.0
            )

            match_result = parse_llm_json(response.response)
            recalculate_scores(match_result)

            return match_result
        except json.JSONDecodeError as e:
            raw = response.response if response else "N/A"
            logger.error(f"Failed to parse Matcher JSON output: {e}\nRaw Output: {raw}")
            raise ValueError("LLM returned invalid matching JSON") from e
        except Exception as e:
            logger.error(f"Unexpected error during matching: {e}")
            raise


job_fit_matcher = JobFitMatcher()
