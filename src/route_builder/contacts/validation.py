"""Diagnostics and source-total reconciliation for contact extraction."""

import re
from collections import Counter

from .adapters import ParsedContacts
from .pdf import ExtractedPDF


def expected_people(document: ExtractedPDF, layout: str) -> int | None:
    cover = document.page_text[0]
    if layout == "ys930":
        match = re.search(r"\bPeople:\s*(\d+)\b", cover)
        return int(match.group(1)) if match else None
    counts = re.findall(r"\bTurf\s+\d{2}\s*\n\s*(\d+)\s*\n\s*\d+\b", cover)
    return sum(map(int, counts)) if counts else None


def validate(document: ExtractedPDF, layout: str, parsed: ParsedContacts) -> dict:
    expected = expected_people(document, layout)
    if expected is None:
        raise ValueError("Printed people total was not found; manual count validation required")
    if len(parsed.records) != expected:
        raise ValueError(f"Extracted {len(parsed.records)} people; printed people total is {expected}")
    if layout == "ys930" and parsed.header_count == 0:
        raise ValueError("No gray group headers were parsed")
    if layout == "ys930" and any(record.turf for record in parsed.records):
        raise ValueError("YS930 has no verified turf metadata")
    if layout == "ys925" and any(not record.turf for record in parsed.records):
        raise ValueError("A YS925 contact has no turf")
    addresses = Counter(record.address for record in parsed.records)
    return {
        "layout": layout,
        "pdf_pages": len(document.pages),
        "printed_people": expected,
        "extracted_people": len(parsed.records),
        "group_or_turf_headers": parsed.header_count,
        "contacts_by_page": parsed.page_counts,
        "page_numbers_with_carried_header": parsed.carried_pages,
        "missing_phone_count": sum(not record.phone for record in parsed.records),
        "shared_address_count": sum(count > 1 for count in addresses.values()),
        "assembled_address_count": parsed.assembled_address_count,
        "turf_counts": dict(Counter(record.turf for record in parsed.records if record.turf)),
    }
