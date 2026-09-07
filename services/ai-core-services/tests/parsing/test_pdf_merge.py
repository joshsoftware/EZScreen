from src.parsing.ocr.pdf_ocr import PageOCRResult
from src.parsing.pdf_merge import merge_pdf_extractions


def test_merge_pdf_extractions_includes_docling_and_all_ocr_pages():
    ocr_pages = [
        PageOCRResult(page_number=1, text="OCR line 1", status="ok"),
        PageOCRResult(page_number=2, text="[no OCR text detected]", status="empty"),
    ]

    merged = merge_pdf_extractions("Docling body text", ocr_pages)

    assert "=== DOCLING EXTRACTION ===" in merged
    assert "Docling body text" in merged
    assert "=== RAPID OCR (ALL PAGES) ===" in merged
    assert "--- PAGE 1 ---" in merged
    assert "OCR line 1" in merged
    assert "--- PAGE 2 ---" in merged
    assert "[no OCR text detected]" in merged


def test_merge_pdf_extractions_preserves_overlapping_content():
    docling = "Python developer at Acme Corp"
    ocr_pages = [
        PageOCRResult(page_number=1, text="Python developer at Acme Corp", status="ok"),
    ]

    merged = merge_pdf_extractions(docling, ocr_pages)

    assert merged.count("Python developer at Acme Corp") == 2


def test_merge_pdf_extractions_handles_empty_ocr():
    merged = merge_pdf_extractions("Docling only", [])

    assert "Docling only" in merged
    assert "[OCR unavailable or PDF has no pages]" in merged
