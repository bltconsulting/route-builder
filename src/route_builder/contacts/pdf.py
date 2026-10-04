"""Embedded-text inspection and positional extraction; no contact data leaves the machine."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TextLine:
    page: int
    x: float
    y: float
    text: str


@dataclass(frozen=True)
class ExtractedPDF:
    pages: tuple[tuple[TextLine, ...], ...]
    page_text: tuple[str, ...]


def extract_embedded_text(path: Path) -> ExtractedPDF:
    try:
        import pymupdf
    except ImportError as error:
        raise RuntimeError("Install the contacts extra: pip install -e '.[contacts]'") from error

    pages = []
    page_text = []
    with pymupdf.open(path) as document:
        for number, page in enumerate(document, 1):
            page_text.append(page.get_text("text"))
            lines = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", ()):
                    value = "".join(span["text"] for span in line["spans"]).strip()
                    if value:
                        lines.append(TextLine(number, line["bbox"][0], line["bbox"][1], value))
            pages.append(tuple(sorted(lines, key=lambda item: (item.y, item.x))))
    if not any(page_text):
        raise ValueError("No embedded PDF text found; this file needs local OCR and manual review")
    return ExtractedPDF(tuple(pages), tuple(page_text))
