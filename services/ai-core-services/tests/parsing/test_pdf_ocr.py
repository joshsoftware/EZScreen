from unittest.mock import MagicMock, patch

import pytest

from src.parsing.ocr.pdf_ocr import PageOCRResult, extract_all_pages_ocr


def _make_pdf_mock(page_count: int):
    pdf = MagicMock()
    pdf.__len__ = MagicMock(return_value=page_count)
    pages = []
    for _ in range(page_count):
        page = MagicMock()
        bitmap = MagicMock()
        pil_image = MagicMock()
        bitmap.to_pil.return_value = pil_image
        page.render.return_value = bitmap
        pages.append(page)
    pdf.__getitem__ = MagicMock(side_effect=lambda i: pages[i])
    return pdf


@patch("src.parsing.ocr.pdf_ocr.pdfium")
@patch("src.parsing.ocr.pdf_ocr._get_ocr_engine")
def test_extract_all_pages_ocr_processes_every_page(mock_get_ocr, mock_pdfium):
    mock_pdfium.PdfDocument.return_value = _make_pdf_mock(3)
    ocr = MagicMock()
    ocr.side_effect = [
        MagicMock(txts=["Line A"]),
        MagicMock(txts=[]),
        MagicMock(txts=["Line C"]),
    ]
    mock_get_ocr.return_value = ocr

    results = extract_all_pages_ocr("/tmp/resume.pdf")

    assert len(results) == 3
    assert [r.page_number for r in results] == [1, 2, 3]
    assert results[0].status == "ok"
    assert results[0].text == "Line A"
    assert results[1].status == "empty"
    assert results[1].text == "[no OCR text detected]"
    assert results[2].status == "ok"
    assert ocr.call_count == 3


@patch("src.parsing.ocr.pdf_ocr.pdfium")
@patch("src.parsing.ocr.pdf_ocr._get_ocr_engine")
def test_extract_all_pages_ocr_records_page_error(mock_get_ocr, mock_pdfium):
    pdf = _make_pdf_mock(1)
    pdf.__getitem__.side_effect = RuntimeError("render failed")
    mock_pdfium.PdfDocument.return_value = pdf
    mock_get_ocr.return_value = MagicMock()

    results = extract_all_pages_ocr("/tmp/resume.pdf")

    assert len(results) == 1
    assert results[0].status == "error"
    assert "OCR failed" in results[0].text


@patch("src.parsing.ocr.pdf_ocr.settings")
@patch("src.parsing.ocr.pdf_ocr.pdfium")
@patch("src.parsing.ocr.pdf_ocr._get_ocr_engine")
def test_extract_all_pages_ocr_respects_max_pages(mock_get_ocr, mock_pdfium, mock_settings):
    mock_settings.ocr_max_pages = 2
    mock_settings.ocr_scale = 3.0
    mock_pdfium.PdfDocument.return_value = _make_pdf_mock(5)
    ocr = MagicMock(return_value=MagicMock(txts=["text"]))
    mock_get_ocr.return_value = ocr

    results = extract_all_pages_ocr("/tmp/resume.pdf")

    assert ocr.call_count == 2
    assert len(results) == 3  # 2 pages + truncation marker
    assert results[-1].text.startswith("[TRUNCATED:")


@patch("src.parsing.ocr.pdf_ocr.pdfium", None)
@patch("src.parsing.ocr.pdf_ocr.RapidOCR", None)
def test_extract_all_pages_ocr_disabled_when_libs_missing():
    assert extract_all_pages_ocr("/tmp/resume.pdf") == []
