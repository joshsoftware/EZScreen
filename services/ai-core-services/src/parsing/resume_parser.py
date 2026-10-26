import asyncio
import json
import os
import zipfile
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


def detect_resume_format(path: str) -> Optional[str]:
    """Return ".pdf", ".docx" or ".doc" from the file's own bytes, or None.

    The upload page accepts a file by MIME type even when its name has no
    (or the wrong) extension, so the stored name alone isn't reliable
    (Bug-028).
    """
    with open(path, "rb") as file:
        head = file.read(1024)
    # The PDF spec lets a few junk bytes precede the header.
    if b"%PDF-" in head:
        return ".pdf"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return ".doc"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as archive:
                if "word/document.xml" in archive.namelist():
                    return ".docx"
        except zipfile.BadZipFile:
            return None
    return None


def _unsupported_format_message(detected: Optional[str], name_ext: str) -> str:
    if detected == ".doc":
        # Legacy binary Word; Docling can't read it.
        return (
            "Unsupported resume format: old Word .doc file. "
            "Save it as DOCX or PDF and upload again."
        )
    return (
        f"Unsupported resume format: {name_ext or 'unknown'}. "
        "Only PDF and DOCX resumes are supported."
    )


def _string_list(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def normalize_highlights(parsed: dict) -> None:
    """Keep role sub-headings and rebuild the flat highlights list from them.

    The timeline shows highlight_groups (sub-heading + bullets, Bug-036);
    skill-years, job fit and question generation keep reading the flat
    highlights list.
    """
    experience = parsed.get("experience")
    roles = experience.get("roles") if isinstance(experience, dict) else None
    for role in roles if isinstance(roles, list) else []:
        if not isinstance(role, dict):
            continue
        groups = []
        for group in role.get("highlight_groups") or []:
            if not isinstance(group, dict):
                continue
            points = _string_list(group.get("highlights"))
            heading = group.get("heading")
            heading = heading.strip() if isinstance(heading, str) and heading.strip() else None
            if points or heading:
                groups.append({"heading": heading, "highlights": points})
        if not groups:
            # Model answered in the old flat shape.
            points = _string_list(role.get("highlights"))
            groups = [{"heading": None, "highlights": points}] if points else []
        role["highlight_groups"] = groups
        role["highlights"] = [point for group in groups for point in group["highlights"]]

    projects = []
    for project in parsed.get("projects") or []:
        if not isinstance(project, dict):
            continue
        name = project.get("name")
        name = name.strip() if isinstance(name, str) else ""
        points = _string_list(project.get("highlights"))
        if name or points:
            projects.append(
                {
                    "name": name or None,
                    "tech_stack": _string_list(project.get("tech_stack")),
                    "highlights": points,
                }
            )
    parsed["projects"] = projects


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

                name_ext = os.path.splitext(tmp_path)[1].lower()
                ext = await asyncio.to_thread(detect_resume_format, tmp_path)
                if ext not in SUPPORTED_RESUME_EXTENSIONS:
                    raise ValueError(_unsupported_format_message(ext, name_ext))
                if os.path.splitext(tmp_path)[1] != ext:
                    # Docling picks its reader from the extension.
                    fixed_path = os.path.splitext(tmp_path)[0] + ext
                    os.replace(tmp_path, fixed_path)
                    tmp_path = fixed_path
                    logger.info(
                        "Resume type taken from file contents",
                        extra={"s3_key": s3_key, "name_ext": name_ext, "detected": ext},
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

                normalize_highlights(parsed_data)
                recalculate_experience(parsed_data, resume_text=markdown_text)
                return parsed_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON output: {e}\nRaw Output: {response.response}")
                raise ValueError("LLM returned invalid JSON") from e

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


resume_parser = ResumeParser()
