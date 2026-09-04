from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from src.core.config import settings
from src.core.logger import logger


def _build_converter() -> DocumentConverter:
    if settings.docling_do_ocr:
        logger.info("Initializing Docling DocumentConverter (full pipeline with OCR)")
        return DocumentConverter()

    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
    )
    logger.info(
        "Initializing Docling DocumentConverter (text-layer only, OCR disabled)",
        extra={"do_ocr": False},
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )


class DoclingWrapper:
    def __init__(self):
        self.converter = _build_converter()

    def extract_markdown(self, file_path: str) -> tuple[str, int]:
        """
        Parses a local document (e.g. PDF) and returns the extracted Markdown text
        along with the number of pages in the document.
        """
        logger.info(f"Docling extracting markdown from: {file_path}")
        result = self.converter.convert(file_path)
        markdown = result.document.export_to_markdown()
        page_count = result.document.num_pages() if hasattr(result.document, 'num_pages') else 1
        logger.info(
            "Docling extraction complete",
            extra={"file_path": file_path, "markdown_chars": len(markdown), "pages": page_count},
        )
        return markdown, page_count


docling_wrapper = DoclingWrapper()
