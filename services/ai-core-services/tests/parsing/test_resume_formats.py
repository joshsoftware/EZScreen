import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.parsing import resume_parser as rp

PDF_BYTES = b"%PDF-1.4\n%fake\n"
DOC_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64


def _write_docx(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", "<w:document/>")


def _write(path, kind):
    if kind == "docx":
        _write_docx(path)
    elif kind == "pdf":
        path.write_bytes(PDF_BYTES)
    elif kind == "doc":
        path.write_bytes(DOC_BYTES)
    else:
        path.write_bytes(b"plain text resume")


def _parser():
    llm = MagicMock()
    llm.openai_chat_generate = AsyncMock(
        return_value=MagicMock(response='{"personal_info": {"first_name": "Priya"}, "experience": {"roles": []}}')
    )
    return rp.ResumeParser(llm_client=llm)


async def _parse(path):
    with patch.object(rp.storage_client, "download_to_tempfile", return_value=str(path)), patch.object(
        rp.docling_wrapper, "extract_markdown", return_value=("# Priya Sharma\n- Java", 1)
    ) as docling, patch.object(rp, "extract_all_pages_ocr", return_value=[]) as ocr, patch.object(
        rp, "merge_pdf_extractions", side_effect=lambda md, pages: md
    ), patch.object(rp, "recalculate_experience"):
        parsed = await _parser().parse_s3_file(f"orgs/o/jobs/j/resumes/{path.name}")
    return parsed, docling, ocr


@pytest.mark.parametrize(
    "file_name, kind, ocr_expected",
    [("resume.docx", "docx", False), ("resume.pdf", "pdf", True)],
)
@pytest.mark.asyncio
async def test_pdf_and_docx_resumes_are_parsed(tmp_path, file_name, kind, ocr_expected):
    """Bug-025: DOCX was rejected with "Only PDF resumes are supported"."""
    path = tmp_path / file_name
    _write(path, kind)
    parsed, _, ocr = await _parse(path)

    assert parsed["personal_info"]["first_name"] == "Priya"
    assert ocr.called is ocr_expected


@pytest.mark.parametrize(
    "file_name, kind, read_as",
    [
        ("Resume", "pdf", ".pdf"),  # no extension
        ("Resume.PDF", "pdf", ".pdf"),
        ("resume.pdf", "docx", ".docx"),  # misnamed Word file
    ],
)
@pytest.mark.asyncio
async def test_resume_type_comes_from_file_contents(tmp_path, file_name, kind, read_as):
    """Bug-028: a real PDF/DOCX whose name lacked the right extension was
    reported as "Unsupported File"."""
    path = tmp_path / file_name
    _write(path, kind)
    parsed, docling, _ = await _parse(path)

    assert parsed["personal_info"]["first_name"] == "Priya"
    assert docling.call_args.args[0].endswith(read_as)


@pytest.mark.parametrize(
    "file_name, kind, message",
    [
        ("resume.txt", "text", "Only PDF and DOCX"),
        ("resume.pdf", "text", "Only PDF and DOCX"),  # renamed, not really a PDF
        ("resume.doc", "doc", "old Word .doc file"),
    ],
)
@pytest.mark.asyncio
async def test_other_formats_are_rejected_with_a_clear_message(tmp_path, file_name, kind, message):
    path = tmp_path / file_name
    _write(path, kind)
    with pytest.raises(ValueError, match=message):
        await _parse(path)
