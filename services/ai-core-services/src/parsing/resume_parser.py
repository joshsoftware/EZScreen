import asyncio
import json
import os
from datetime import datetime
from typing import Optional

from src.common.llm_utils import parse_llm_json
from src.core.logger import logger
from src.core.storage import storage_client
from src.llm.client import OllamaClient
from src.parsing.docling_wrapper import docling_wrapper
from src.parsing.experience_calculator import recalculate_experience
from src.parsing.prompt_builder import resume_prompt_builder

# Restrict OCR to a single concurrent thread to prevent PyTorch OpenMP thread deadlocks,
# while still offloading it to a background thread so the FastAPI event loop is NOT blocked!
ocr_semaphore = asyncio.Semaphore(1)


class ResumeParser:
    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm_client = llm_client or OllamaClient()

    async def parse_s3_file(self, s3_key: str) -> dict:
        """Downloads from S3, extracts markdown, and parses using LLM."""
        tmp_path = await asyncio.to_thread(storage_client.download_to_tempfile, s3_key)

        try:
            async with ocr_semaphore:
                markdown_text = await asyncio.to_thread(docling_wrapper.extract_markdown, tmp_path)

            current_date = datetime.now().strftime("%Y-%m-%d")
            prompt = resume_prompt_builder.build(markdown_text, current_date)

            logger.info("Sending resume extraction prompt to LLM")
            response = await self.llm_client.openai_chat_generate(
                prompt=prompt, temperature=0.1, timeout=120.0
            )

            try:
                parsed_data = parse_llm_json(response.response)
                if isinstance(parsed_data, dict) and "parsed_resume" in parsed_data:
                    parsed_data = parsed_data["parsed_resume"]

                recalculate_experience(parsed_data)
                return parsed_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON output: {e}\nRaw Output: {response.response}")
                raise ValueError("LLM returned invalid JSON") from e

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


resume_parser = ResumeParser()
