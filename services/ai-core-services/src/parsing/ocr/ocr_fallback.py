import os
import re
from typing import Optional, Tuple
from dataclasses import dataclass
from src.core.logger import logger

try:
    import pypdfium2 as pdfium
    from rapidocr import RapidOCR
except ImportError:
    logger.warning("pypdfium2 or rapidocr not installed. OCR fallback will be disabled.")
    pdfium = None
    RapidOCR = None

# Using the same regexes for consistency
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

OCR_SCALE = 3.0
HEADER_CROP_RATIO = 0.35

@dataclass
class OCRContactResult:
    email: Optional[str]
    phone: Optional[str]
    source: str

def _extract_candidates(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts email and phone from raw text."""
    clean_text = text.replace("\n", "").replace(" ", "")  # For broken emails/phones
    
    # Try to find in clean text first, fallback to original
    email_match = EMAIL_RE.search(clean_text) or EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(clean_text) or PHONE_RE.search(text)
    
    email = email_match.group(0) if email_match else None
    phone = phone_match.group(0) if phone_match else None
    
    return email, phone

def recover_full_document(pdf_path: str, start_page: int = 1) -> str:
    """Runs RapidOCR on subsequent pages of the document to recover graphical text."""
    if not pdfium or not RapidOCR:
        return ""
        
    logger.info(f"Running Full Document OCR recovery for pages {start_page}+ on {pdf_path}")
    ocr = RapidOCR()
    pdf = pdfium.PdfDocument(pdf_path)
    
    full_text = []
    
    # Only scan if the document has more pages than the start_page
    if len(pdf) <= start_page:
        return ""
        
    for i in range(start_page, len(pdf)):
        page = pdf[i]
        bitmap = page.render(scale=OCR_SCALE)
        pil_image = bitmap.to_pil()
        
        page_path = f"{pdf_path}_page_{i}.png"
        pil_image.save(page_path)
        
        result = ocr(page_path)
        if result and hasattr(result, "txts") and result.txts:
            full_text.append(f"--- PAGE {i+1} OCR ---")
            full_text.extend(result.txts)
            
        if os.path.exists(page_path):
            os.remove(page_path)
            
    return "\n".join(full_text)

def recover_contact_info(pdf_path: str, missing_email: bool, missing_phone: bool) -> OCRContactResult:
    if not pdfium or not RapidOCR:
        return OCRContactResult(None, None, "disabled")
        
    logger.info(f"Starting targeted OCR contact recovery for {pdf_path}")
    ocr = RapidOCR()
    pdf = pdfium.PdfDocument(pdf_path)
    
    if len(pdf) == 0:
        return OCRContactResult(None, None, "empty_pdf")
    
    # Check page 1
    page = pdf[0]
    
    # Render for Pass 1 (Top 35% crop)
    bitmap = page.render(scale=OCR_SCALE)
    pil_image = bitmap.to_pil()
    
    crop_height = int(pil_image.height * HEADER_CROP_RATIO)
    crop = pil_image.crop((0, 0, pil_image.width, crop_height))
    
    crop_path = f"{pdf_path}_ocr_fallback_crop.png"
    crop.save(crop_path)
    
    logger.info("Running Pass 1: Header Crop OCR")
    result = ocr(crop_path)
    
    email = None
    phone = None
    
    if result and hasattr(result, "txts") and result.txts:
        raw_text = "\n".join(result.txts)
        email, phone = _extract_candidates(raw_text)
        
    if os.path.exists(crop_path):
        os.remove(crop_path)
        
    # Check if we recovered what we needed
    recovered_email = email if missing_email else None
    recovered_phone = phone if missing_phone else None
    
    if (missing_email and not recovered_email) or (missing_phone and not recovered_phone):
        logger.info("Running Pass 2: Full Page OCR")
        full_path = f"{pdf_path}_ocr_fallback_full.png"
        pil_image.save(full_path)
        
        result_full = ocr(full_path)
        if result_full and hasattr(result_full, "txts") and result_full.txts:
            raw_text_full = "\n".join(result_full.txts)
            e_full, p_full = _extract_candidates(raw_text_full)
            if not recovered_email and e_full: recovered_email = e_full
            if not recovered_phone and p_full: recovered_phone = p_full
            
        if os.path.exists(full_path):
            os.remove(full_path)
            
    source = "header_crop" if recovered_email or recovered_phone else "none"
    if not email and not phone and (recovered_email or recovered_phone):
        source = "full_page"
        
    return OCRContactResult(recovered_email, recovered_phone, source)
