from docling.document_converter import DocumentConverter
from src.core.logger import logger

class DoclingWrapper:
    def __init__(self):
        self.converter = DocumentConverter()
        logger.info("Initialized Docling DocumentConverter")

    def extract_markdown(self, file_path: str) -> str:
        """
        Parses a local document (e.g. PDF) and returns the extracted Markdown text.
        """
        logger.info(f"Docling extracting markdown from: {file_path}")
        result = self.converter.convert(file_path)
        return result.document.export_to_markdown()

docling_wrapper = DoclingWrapper()
