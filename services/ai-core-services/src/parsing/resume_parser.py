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
from src.parsing.document_quality import validate_markdown
from src.parsing.ocr.ocr_fallback import recover_contact_info, recover_full_document

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
                markdown_text, page_count = await asyncio.to_thread(docling_wrapper.extract_markdown, tmp_path)
                
                # Quality Validation (pass page_count for graphical detection)
                quality = validate_markdown(markdown_text, page_count)
                logger.info(f"Markdown validation: {quality}")
                
                if quality.needs_contact_recovery:
                    logger.info("Triggering Targeted OCR Fallback for Contact Recovery")
                    ocr_result = await asyncio.to_thread(
                        recover_contact_info, 
                        tmp_path, 
                        not quality.has_email, 
                        not quality.has_phone
                    )
                    
                    if ocr_result.email or ocr_result.phone:
                        logger.info(f"Recovered contact info from {ocr_result.source}")
                        recovery_block = "--- OCR RECOVERED CONTACT INFO ---\n"
                        if ocr_result.email:
                            recovery_block += f"Email: {ocr_result.email}\n"
                        if ocr_result.phone:
                            recovery_block += f"Phone: {ocr_result.phone}\n"
                        recovery_block += "----------------------------------\n\n"
                        
                        markdown_text = recovery_block + markdown_text
                
                # OCR is invoked when:
                # 1. Contact info is missing (needs_contact_recovery) — likely a graphical PDF
                # 2. Text content is too sparse per page (image-heavy resume like Canva)
                # Both conditions are combined into is_likely_graphical
                if quality.is_likely_graphical:
                    logger.info(f"Graphical/image-heavy resume detected (avg chars/page: {quality.character_count / max(page_count, 1):.0f}). Running full document OCR.")
                    full_ocr_text = await asyncio.to_thread(recover_full_document, tmp_path, 0)
                    if full_ocr_text:
                        markdown_text += "\n\n--- FULL DOCUMENT OCR RECOVERY (Graphical Fallback) ---\n"
                        markdown_text += full_ocr_text
                else:
                    logger.info("Native text extraction sufficient. Bypassing OCR entirely.")

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
