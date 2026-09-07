from src.core.logger import logger
from src.parsing.ocr.pdf_ocr import PageOCRResult


def merge_pdf_extractions(docling_markdown: str, ocr_pages: list[PageOCRResult]) -> str:
    """Combine Docling markdown and per-page OCR into one LLM input. Preserve all information."""
    sections: list[str] = ["=== DOCLING EXTRACTION ===", docling_markdown or ""]

    sections.append("\n=== RAPID OCR (ALL PAGES) ===")
    if not ocr_pages:
        sections.append("[OCR unavailable or PDF has no pages]")
    else:
        for page in ocr_pages:
            sections.append(f"\n--- PAGE {page.page_number} ---")
            sections.append(page.text)

    merged = "\n".join(sections)
    logger.info(
        "Merged PDF extractions",
        extra={
            "docling_chars": len(docling_markdown or ""),
            "ocr_pages": len(ocr_pages),
            "ocr_ok": sum(1 for p in ocr_pages if p.status == "ok"),
            "ocr_empty": sum(1 for p in ocr_pages if p.status == "empty"),
            "ocr_error": sum(1 for p in ocr_pages if p.status == "error"),
            "merged_chars": len(merged),
        },
    )
    return merged
