"""Layout-specific parsing for verified contact tables."""

import re
from collections import Counter
from dataclasses import dataclass

from .pdf import ExtractedPDF, TextLine
from .schema import ContactRecord

PHONE = re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b")
HOUSE = re.compile(r"^\d+[A-Za-z]?(?:\s+.*)?$")
HOUSE_ONLY = re.compile(r"^(\d+[A-Za-z]?)(?:\s+((?:Apt|Unit|Suite|Ste|#)\s+\S+))?$", re.I)
TURF = re.compile(r"\bTurf\s+(\d{2})\b")
YS930_HEADER = re.compile(r"^(.+?\s-\s\d{3})\s*·\s*(.+?)\s*·\s*(.+?)$")
YS_REQUESTS_HEADER = re.compile(
    r"^(.+?\s-\s\d{3})\s*·\s*(\d+[A-Za-z]?)\s*·\s*(.+?)\s*·\s*(.+?)$"
)


@dataclass(frozen=True)
class ParsedContacts:
    records: tuple[ContactRecord, ...]
    page_counts: dict[int, int]
    header_count: int
    carried_pages: tuple[int, ...]
    assembled_address_count: int


def detect_layout(document: ExtractedPDF) -> str:
    if document.page_text and "Turf Packet Summary" in document.page_text[0]:
        return "ys925"
    if any(YS_REQUESTS_HEADER.fullmatch(line.text) for page in document.pages for line in page):
        return "ysrequests"
    if any(YS930_HEADER.match(line.text) for page in document.pages for line in page):
        return "ys930"
    raise ValueError("Unsupported layout; inspect representative pages before adding an adapter")


def _address_line(line: TextLine) -> bool:
    return 14 <= line.x <= 40 and bool(HOUSE.fullmatch(line.text))


def _address(value: str, street: str) -> tuple[str, bool]:
    if not street:
        return value, False
    simple = HOUSE_ONLY.fullmatch(value)
    if simple:
        house, unit = simple.groups()
        return f"{house} {street}" + (f" {unit}" if unit else ""), True
    main = re.split(r"\s+(?:Apt|Unit|Suite|Ste|#)\b", value, maxsplit=1, flags=re.I)[0]
    if not main.casefold().endswith(street.casefold()):
        raise ValueError(f"Address does not match current street header: {value!r} / {street!r}")
    return value, False


def _contact_on_line(lines: tuple[TextLine, ...], address: TextLine) -> tuple[str, str]:
    names = [line.text for line in lines if 280 <= line.x < 450 and abs(line.y - address.y) < 0.7]
    if len(names) != 1 or "," not in names[0]:
        raise ValueError(f"Page {address.page}: address at y={address.y:.1f} has {len(names)} paired names")
    details = [line.text for line in lines if 280 <= line.x < 450 and 5 < line.y - address.y < 12]
    if len(details) != 1:
        raise ValueError(f"Page {address.page}: address at y={address.y:.1f} has {len(details)} detail lines")
    phones = PHONE.findall(details[0])
    if len(phones) > 1:
        raise ValueError(f"Page {address.page}: multiple phones on one contact row")
    return names[0], phones[0] if phones else ""


def parse_contacts(document: ExtractedPDF, layout: str) -> ParsedContacts:
    if layout not in {"ys925", "ys930", "ysrequests"}:
        raise ValueError(f"Unsupported adapter: {layout}")
    records = []
    page_counts: Counter[int] = Counter()
    header_count = assembled = 0
    carried_pages = []
    precinct = town = street = turf = house_number = ""
    for page_number, lines in enumerate(document.pages, 1):
        if layout == "ys925" and page_number == 1:
            continue  # Summary table is not a contact page or a turf heading.
        has_name_column = any(280 <= item.x < 450 and "," in item.text for item in lines)
        first_address = next((line.y for line in lines if _address_line(line)), None)
        if first_address is not None and layout in {"ys930", "ysrequests"} and precinct:
            pattern = YS930_HEADER if layout == "ys930" else YS_REQUESTS_HEADER
            first_header = next((line.y for line in lines if pattern.fullmatch(line.text)), None)
            if first_header is None or first_address < first_header:
                carried_pages.append(page_number)
        for line in lines:
            if layout in {"ys930", "ysrequests"}:
                pattern = YS930_HEADER if layout == "ys930" else YS_REQUESTS_HEADER
                header = pattern.fullmatch(line.text)
                if header and 15 <= line.x <= 40:
                    if layout == "ysrequests":
                        precinct, house_number, street, town = (part.strip() for part in header.groups())
                    else:
                        precinct, town, street = (part.strip() for part in header.groups())
                    header_count += 1
                    continue
            else:
                heading = TURF.search(line.text) if "Turf" in line.text else None
                if heading and "People /" in " ".join(item.text for item in lines[:4]):
                    turf = f"Turf {heading.group(1)}"
                    header_count += 1
            if not _address_line(line):
                continue
            if layout == "ys925" and not has_name_column:
                continue  # Repeated canvass script pages contain numbered questions.
            if layout in {"ys930", "ysrequests"} and not precinct:
                continue  # Cover/script pages precede the first gray group header.
            if layout == "ys925" and not turf:
                continue  # Cover/script pages precede the first turf packet heading.
            if layout in {"ys930", "ysrequests"} and not all((precinct, town, street)):
                raise ValueError(f"Page {page_number}: contact before a complete group header")
            if layout == "ysrequests" and not house_number:
                raise ValueError(f"Page {page_number}: contact before a numbered group header")
            if layout == "ys925" and not turf:
                raise ValueError(f"Page {page_number}: contact before a turf heading")
            name, phone = _contact_on_line(lines, line)
            if layout == "ysrequests":
                printed_number = re.match(r"^\d+[A-Za-z]?\b", line.text)
                if not printed_number or printed_number.group() != house_number:
                    raise ValueError(
                        f"Page {page_number}: address does not match current house-number header: "
                        f"{line.text!r} / {house_number!r}"
                    )
                if HOUSE_ONLY.fullmatch(line.text):
                    raise ValueError(f"Page {page_number}: expected a full printed address")
            address, was_assembled = _address(line.text, street if layout in {"ys930", "ysrequests"} else "")
            assembled += was_assembled
            records.append(ContactRecord(name, address, phone, turf, precinct, town, street))
            page_counts[page_number] += 1
    return ParsedContacts(tuple(records), dict(page_counts), header_count, tuple(carried_pages), assembled)
