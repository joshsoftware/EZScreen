from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.parsing import resume_parser as rp


def _parser():
    llm = MagicMock()
    llm.openai_chat_generate = AsyncMock(
        return_value=MagicMock(response='{"personal_info": {"first_name": "Priya"}, "experience": {"roles": []}}')
    )
    return rp.ResumeParser(llm_client=llm)


@pytest.mark.parametrize(
    "ext, ocr_expected",
    [(".docx", False), (".pdf", True)],
)
@pytest.mark.asyncio
async def test_pdf_and_docx_resumes_are_parsed(tmp_path, ext, ocr_expected):
    """Bug-025: DOCX was rejected with "Only PDF resumes are supported"."""
    path = tmp_path / f"resume{ext}"
    path.write_bytes(b"x")
    with patch.object(rp.storage_client, "download_to_tempfile", return_value=str(path)), patch.object(
        rp.docling_wrapper, "extract_markdown", return_value=("# Priya Sharma\n- Java", 1)
    ), patch.object(rp, "extract_all_pages_ocr", return_value=[]) as ocr, patch.object(
        rp, "merge_pdf_extractions", side_effect=lambda md, pages: md
    ), patch.object(rp, "recalculate_experience"):
        parsed = await _parser().parse_s3_file(f"orgs/o/jobs/j/resumes/abc-resume{ext}")

    assert parsed["personal_info"]["first_name"] == "Priya"
    assert ocr.called is ocr_expected


@pytest.mark.asyncio
async def test_other_formats_are_rejected_with_a_clear_message(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_bytes(b"x")
    with patch.object(rp.storage_client, "download_to_tempfile", return_value=str(path)):
        with pytest.raises(ValueError, match="Only PDF and DOCX"):
            await _parser().parse_s3_file("orgs/o/jobs/j/resumes/abc-resume.txt")
