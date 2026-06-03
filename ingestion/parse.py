"""Parse PDFs into structured text, detecting section boundaries."""

import re
from pathlib import Path

import fitz  # PyMuPDF

SECTION_PATTERNS = re.compile(
    r"^\s*(abstract|introduction|related work|background|methodology|"
    r"method|methods|approach|experiments?|results?|evaluation|"
    r"discussion|conclusion|references)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_pdf(pdf_path: Path) -> list[dict]:
    """
    Parse a PDF into a list of section dicts.
    Each dict has: {section, text, page_start}
    Falls back to full-text if no section headings detected.
    """
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        print(f"[parse] Cannot open {pdf_path.name}: {e}")
        return []

    pages_text = []
    for page in doc:
        pages_text.append(page.get_text("text"))
    doc.close()

    full_text = "\n".join(pages_text)
    full_text = _clean_text(full_text)

    sections = _split_by_sections(full_text)
    if not sections:
        return [{"section": "full_text", "text": full_text, "page_start": 0}]
    return sections


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _split_by_sections(text: str) -> list[dict]:
    matches = list(SECTION_PATTERNS.finditer(text))
    if not matches:
        return []

    sections = []
    for i, match in enumerate(matches):
        section_name = match.group().strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if len(section_text) > 50:
            sections.append({"section": section_name, "text": section_text, "page_start": 0})

    return sections
