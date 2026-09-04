from dataclasses import dataclass
import re

# Basic Regex for validation
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE)
# Phone regex: matches basic formats, +91, (555), etc.
PHONE_RE = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

# A normal text-based resume page typically has 500+ characters of content.
# If the average is below this, the resume likely contains graphical/image elements.
MIN_CHARS_PER_PAGE = 500

@dataclass
class MarkdownQuality:
    has_email: bool
    has_phone: bool
    character_count: int
    needs_contact_recovery: bool
    is_likely_graphical: bool  # True if content is too sparse (image-heavy resume)

def validate_markdown(markdown: str, page_count: int = 1) -> MarkdownQuality:
    has_email = bool(EMAIL_RE.search(markdown))
    # Remove some common formatting to make phone regex more robust on markdown
    clean_md = markdown.replace("\n", " ").replace("\r", " ")
    has_phone = bool(PHONE_RE.search(clean_md))
    char_count = len(markdown)
    
    needs_contact_recovery = not (has_email and has_phone)
    
    # A graphical resume (Canva, images, etc.) will have very little text per page
    avg_chars_per_page = char_count / max(page_count, 1)
    is_likely_graphical = needs_contact_recovery or avg_chars_per_page < MIN_CHARS_PER_PAGE
    
    return MarkdownQuality(
        has_email=has_email,
        has_phone=has_phone,
        character_count=char_count,
        needs_contact_recovery=needs_contact_recovery,
        is_likely_graphical=is_likely_graphical
    )
