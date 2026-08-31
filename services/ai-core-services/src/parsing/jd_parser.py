import json
from typing import Optional

from src.common.llm_utils import parse_llm_json
from src.core.logger import logger
from src.llm.client import OllamaClient
from src.parsing.jd_prompt_builder import jd_prompt_builder
from src.parsing.schemas import ParsedJDData


class JDParser:
    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm_client = llm_client or OllamaClient()

    async def parse_jd_text(self, jd_text: str) -> dict:
        """Parses JD text or JSON string using LLM to conform to ParsedJDData schema."""
        prompt = jd_prompt_builder.build(jd_text)

        logger.info("Sending JD parsing prompt to LLM")
        response = await self.llm_client.openai_chat_generate(
            prompt=prompt, temperature=0.1, timeout=60.0
        )

        try:
            parsed_data = parse_llm_json(response.response)
            validated_data = ParsedJDData(**parsed_data)
            return validated_data.model_dump()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON output for JD: {e}\nRaw Output: {response.response}")
            raise ValueError("LLM returned invalid JSON for JD") from e
        except Exception as e:
            logger.error(f"Failed to validate JD schema: {e}\nRaw Output: {response.response}")
            raise ValueError(f"LLM returned JSON that does not match schema: {e}") from e


jd_parser = JDParser()
