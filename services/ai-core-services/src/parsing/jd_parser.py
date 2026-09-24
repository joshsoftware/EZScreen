import json
import os
from typing import Optional

from src.common.llm_utils import parse_llm_json
from src.core.logger import logger
from src.llm.client import OllamaClient
from src.parsing.docling_wrapper import docling_wrapper
from src.parsing.jd_form_prompt_builder import jd_form_prefill_prompt_builder
from src.parsing.jd_prompt_builder import jd_prompt_builder
from src.parsing.schemas import JDFormPrefillData, ParsedJDData

_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


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

    def extract_text_from_file(self, file_path: str) -> str:
        """Extract plain text / markdown from an uploaded JD file."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported JD format: {ext or 'unknown'}. "
                "Supported: PDF, DOCX, TXT."
            )
        if ext in {".txt", ".md"}:
            with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read().strip()
            if not text:
                raise ValueError("JD file is empty")
            return text

        markdown, _page_count = docling_wrapper.extract_markdown(file_path)
        text = (markdown or "").strip()
        if not text:
            raise ValueError("Could not extract text from JD file")
        return text

    async def sectionize_for_form(self, jd_text: str) -> dict:
        """Map raw JD text into Create Job form fields + needs_review leftovers."""
        prompt = jd_form_prefill_prompt_builder.build(jd_text)
        logger.info("Sending JD form-prefill prompt to LLM")
        response = await self.llm_client.openai_chat_generate(
            prompt=prompt, temperature=0.1, timeout=90.0
        )
        try:
            parsed_data = parse_llm_json(response.response)
            validated = JDFormPrefillData(**parsed_data)
            return validated.model_dump()
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse LLM JSON for JD form prefill: %s\nRaw: %s",
                e,
                response.response,
            )
            raise ValueError("LLM returned invalid JSON for JD form prefill") from e
        except Exception as e:
            logger.error(
                "Failed to validate JD form prefill schema: %s\nRaw: %s",
                e,
                response.response,
            )
            raise ValueError(
                f"LLM returned JSON that does not match form-prefill schema: {e}"
            ) from e


jd_parser = JDParser()
