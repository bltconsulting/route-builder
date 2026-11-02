"""Parse yard-sign PDFs with address metadata in each gray row header."""

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


HEADER = re.compile(r"^(.+? - \d{3})\s*·\s*(.+?)\s*·\s*(\d+[A-Za-z]?)\s*·\s*(.+?)$")
PHONE = re.compile(r"^\(\d{3}\)\s*\d{3}-\d{4}$")
NAME = re.compile(r"^[^,]+,\s*[^,]+$")
FIELDS = ["Name", "Address", "Phone", "Turf", "Precinct", "Town", "Street"]


@dataclass(frozen=True)
class Line:
    page: int
    x: float
    y: float
    text: str


def extract(path: Path) -> tuple[list[list[Line]], int]:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Install pymupdf to parse this PDF") from exc
    pages = []
    printed = None
    with pymupdf.open(path) as document:
        for number, page in enumerate(document, 1):
            match = re.search(r"\bPeople:\s*(\d+)", page.get_text())
            if match:
                value = int(match.group(1))
                if printed is not None and printed != value:
                    raise ValueError("Conflicting printed people totals")
                printed = value
            lines = []
            for block in page.get_text("dict")["blocks"]:
                for raw in block.get("lines", ()):
                    text = "".join(span["text"] for span in raw["spans"]).strip()
                    if text:
                        lines.append(Line(number, raw["bbox"][0], raw["bbox"][1], text))
            pages.append(sorted(lines, key=lambda line: (line.y, line.x)))
    if printed is None:
        raise ValueError("No printed People total found")
    return pages, printed


def parse_pages(pages: list[list[Line]]) -> tuple[list[dict[str, str]], dict]:
    records = []
    counts: Counter[int] = Counter()
    headers = 0
    carried = []
    pending = None
    for page_number, lines in enumerate(pages, 1):
        if pending:
            carried.append(page_number)
        for line in lines:
            header = HEADER.fullmatch(line.text) if 15 <= line.x <= 40 else None
            if header:
                if pending:
                    raise ValueError(f"Page {line.page}: new header before a name for {pending['Address']}")
                precinct, town, house, street = (part.strip() for part in header.groups())
                pending = {"Name": "", "Address": f"{house} {street}", "Phone": "", "Turf": "",
                           "Precinct": precinct, "Town": town, "Street": street}
                headers += 1
                continue
            if not (15 <= line.x <= 40 and NAME.fullmatch(line.text)):
                continue
            if not pending:
                if headers:
                    raise ValueError(f"Page {line.page}: name without an address header: {line.text}")
                continue
            phones = [other.text for other in lines if 160 <= other.x <= 270
                      and abs(other.y - line.y) < 0.7 and PHONE.fullmatch(other.text)]
            if len(phones) > 1:
                raise ValueError(f"Page {line.page}: multiple phones for {line.text}")
            pending["Name"] = line.text
            pending["Phone"] = phones[0] if phones else ""
            records.append(pending)
            counts[page_number] += 1
            pending = None
    if pending:
        raise ValueError(f"Last address header has no name: {pending['Address']}")
    if not records or headers != len(records):
        raise ValueError(f"Expected one person per header; got {headers} headers and {len(records)} people")
    return records, {"page_counts": dict(counts), "header_count": headers,
                     "carried_pages": carried, "blank_phone_count": sum(not row['Phone'] for row in records)}


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("pdf", type=Path)
    cli.add_argument("--output", type=Path)
    cli.add_argument("--diagnostics", type=Path)
    args = cli.parse_args()
    pages, printed = extract(args.pdf)
    records, details = parse_pages(pages)
    if len(records) != printed:
        raise ValueError(f"Extracted {len(records)} people; printed total is {printed}")
    diagnostics = {"source": args.pdf.name, "layout": "ys_inline_header", "page_count": len(pages),
                   "printed_people": printed, "extracted_people": len(records), **details}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(records)
    if args.diagnostics:
        args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostics.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
