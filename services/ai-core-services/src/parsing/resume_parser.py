import asyncio
import json
import os
from datetime import datetime
from typing import Awaitable, Callable, Optional

from src.common.llm_utils import parse_llm_json
from src.core.logger import logger
from src.core.storage import storage_client
from src.llm.client import OllamaClient
from src.parsing.docling_wrapper import docling_wrapper
from src.parsing.experience_calculator import recalculate_experience
from src.parsing.ocr.pdf_ocr import extract_all_pages_ocr
from src.parsing.pdf_merge import merge_pdf_extractions
from src.parsing.prompt_builder import resume_prompt_builder

# Restrict OCR to a single concurrent thread to prevent PyTorch OpenMP thread deadlocks,
# while still offloading it to a background thread so the FastAPI event loop is NOT blocked!
ocr_semaphore = asyncio.Semaphore(1)


class ResumeParseCancelled(Exception):
    """Raised when the requesting client went away before extraction started."""


# Resume formats accepted by the upload UIs and core-api (Bug-025).
SUPPORTED_RESUME_EXTENSIONS = frozenset({".pdf", ".docx"})


class ResumeParser:
    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm_client = llm_client or OllamaClient()

    async def parse_s3_file(
        self,
        s3_key: str,
        is_cancelled: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> dict:
        """Downloads from S3, extracts markdown, and parses using LLM."""
        tmp_path = await asyncio.to_thread(storage_client.download_to_tempfile, s3_key)

        try:
            async with ocr_semaphore:
                # The caller may have timed out while we waited for the OCR slot.
                # Skip the work so abandoned requests don't keep the queue backed up.
                if is_cancelled is not None and await is_cancelled():
                    raise ResumeParseCancelled(f"Client disconnected before parsing {s3_key}")

                ext = os.path.splitext(tmp_path)[1].lower()
                if ext not in SUPPORTED_RESUME_EXTENSIONS:
                    raise ValueError(
                        f"Unsupported resume format: {ext or 'unknown'}. "
                        "Only PDF and DOCX resumes are supported."
                    )

                docling_md, page_count = await asyncio.to_thread(
                    docling_wrapper.extract_markdown, tmp_path
                )
                if ext == ".pdf":
                    ocr_pages = await asyncio.to_thread(extract_all_pages_ocr, tmp_path)
                    markdown_text = merge_pdf_extractions(docling_md, ocr_pages)
                    logger.info(
                        "PDF hybrid extraction complete",
                        extra={"page_count": page_count, "ocr_pages": len(ocr_pages)},
                    )
                else:
                    # Word files carry a real text layer (with headings and
                    # bullets), so there's nothing for OCR to recover (Bug-025).
                    markdown_text = docling_md
                    logger.info("DOCX extraction complete", extra={"chars": len(markdown_text)})

                if not markdown_text.strip():
                    raise ValueError(f"No text extracted from {ext.lstrip('.').upper()} resume")

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

                recalculate_experience(parsed_data, resume_text=markdown_text)
                return parsed_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON output: {e}\nRaw Output: {response.response}")
                raise ValueError("LLM returned invalid JSON") from e

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


resume_parser = ResumeParser()
