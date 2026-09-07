from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.parsing.ocr.pdf_ocr import PageOCRResult
from src.parsing.resume_parser import ResumeParser


@pytest.mark.asyncio
async def test_pdf_path_uses_docling_and_ocr_merge():
    parser = ResumeParser(llm_client=MagicMock())
    parser.llm_client.openai_chat_generate = AsyncMock(
        return_value=MagicMock(response='{"parsed_resume": {"primary_skills": ["Python"]}}')
    )

    with (
        patch("src.parsing.resume_parser.storage_client.download_to_tempfile", return_value="/tmp/resume.pdf"),
        patch("src.parsing.resume_parser.os.path.exists", return_value=True),
        patch("src.parsing.resume_parser.os.remove"),
        patch(
            "src.parsing.resume_parser.docling_wrapper.extract_markdown",
            return_value=("Docling text", 2),
        ) as mock_docling,
        patch(
            "src.parsing.resume_parser.extract_all_pages_ocr",
            return_value=[PageOCRResult(page_number=1, text="OCR text", status="ok")],
        ) as mock_ocr,
        patch(
            "src.parsing.resume_parser.merge_pdf_extractions",
            return_value="merged text",
        ) as mock_merge,
        patch("src.parsing.resume_parser.recalculate_experience"),
    ):
        result = await parser.parse_s3_file("resumes/test.pdf")

    mock_docling.assert_called_once_with("/tmp/resume.pdf")
    mock_ocr.assert_called_once_with("/tmp/resume.pdf")
    mock_merge.assert_called_once()
    assert result["primary_skills"] == ["Python"]


@pytest.mark.asyncio
async def test_non_pdf_resume_rejected():
    parser = ResumeParser(llm_client=MagicMock())

    with (
        patch("src.parsing.resume_parser.storage_client.download_to_tempfile", return_value="/tmp/resume.docx"),
        patch("src.parsing.resume_parser.os.path.exists", return_value=True),
        patch("src.parsing.resume_parser.os.remove"),
        patch("src.parsing.resume_parser.docling_wrapper.extract_markdown") as mock_docling,
        patch("src.parsing.resume_parser.extract_all_pages_ocr") as mock_ocr,
    ):
        with pytest.raises(ValueError, match="Only PDF resumes are supported"):
            await parser.parse_s3_file("resumes/test.docx")

    mock_docling.assert_not_called()
    mock_ocr.assert_not_called()
