import tempfile
import os
from dataclasses import dataclass
from typing import Literal

from src.core.config import settings
from src.core.logger import logger

try:
    import pypdfium2 as pdfium
    from rapidocr import RapidOCR
except ImportError:
    logger.warning("pypdfium2 or rapidocr not installed. PDF OCR will be disabled.")
    pdfium = None
    RapidOCR = None

_ocr_engine: "RapidOCR | None" = None


def _get_ocr_engine() -> "RapidOCR | None":
    global _ocr_engine
    if RapidOCR is None:
        return None
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


@dataclass
class PageOCRResult:
    page_number: int  # 1-indexed for display
    text: str
    status: Literal["ok", "empty", "error"]
    error: str | None = None


def _ocr_page_image(ocr: "RapidOCR", page_path: str) -> list[str]:
    result = ocr(page_path)
    if result and hasattr(result, "txts") and result.txts:
        return list(result.txts)
    return []


def extract_all_pages_ocr(pdf_path: str) -> list[PageOCRResult]:
    """Render and OCR every PDF page. Never skip a page silently."""
    if not pdfium or not RapidOCR:
        logger.warning("PDF OCR unavailable — returning empty results for all pages")
        return []

    ocr = _get_ocr_engine()
    if ocr is None:
        return []

    pdf = pdfium.PdfDocument(pdf_path)
    page_count = len(pdf)
    if page_count == 0:
        return []

    max_pages = settings.ocr_max_pages
    pages_to_process = min(page_count, max_pages)
    if page_count > max_pages:
        logger.warning(
            "PDF exceeds ocr_max_pages — truncating OCR",
            extra={"page_count": page_count, "ocr_max_pages": max_pages},
        )

    results: list[PageOCRResult] = []
    scale = settings.ocr_scale

    for page_index in range(pages_to_process):
        page_number = page_index + 1
        page_path: str | None = None
        try:
            page = pdf[page_index]
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                page_path = tmp.name
                pil_image.save(page_path)

            lines = _ocr_page_image(ocr, page_path)
            if lines:
                results.append(
                    PageOCRResult(
                        page_number=page_number,
                        text="\n".join(lines),
                        status="ok",
                    )
                )
            else:
                results.append(
                    PageOCRResult(
                        page_number=page_number,
                        text="[no OCR text detected]",
                        status="empty",
                    )
                )
        except Exception as exc:
            logger.error(
                "OCR failed for page",
                extra={"pdf_path": pdf_path, "page_number": page_number, "error": str(exc)},
            )
            results.append(
                PageOCRResult(
                    page_number=page_number,
                    text=f"[PAGE {page_number}: OCR failed — {exc}]",
                    status="error",
                    error=str(exc),
                )
            )
        finally:
            if page_path and os.path.exists(page_path):
                try:
                    os.remove(page_path)
                except OSError:
                    pass

    if page_count > max_pages:
        results.append(
            PageOCRResult(
                page_number=pages_to_process + 1,
                text=(
                    f"[TRUNCATED: pages {max_pages + 1}..{page_count} "
                    f"not OCR'd due to ocr_max_pages={max_pages}]"
                ),
                status="empty",
            )
        )

    logger.info(
        "PDF OCR complete",
        extra={
            "pdf_path": pdf_path,
            "pages_processed": pages_to_process,
            "ok": sum(1 for r in results if r.status == "ok"),
            "empty": sum(1 for r in results if r.status == "empty"),
            "error": sum(1 for r in results if r.status == "error"),
        },
    )
    return results
