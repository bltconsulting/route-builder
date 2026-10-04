"""Inspect and convert supported contact-table PDFs to organizer CSVs."""

import argparse
import csv
import json
from pathlib import Path

from .adapters import detect_layout, parse_contacts
from .pdf import extract_embedded_text
from .schema import CSV_FIELDS
from .validation import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, help="Write CSV here; omitted for inspection only")
    parser.add_argument("--diagnostics", type=Path, help="Write non-contact validation JSON separately")
    parser.add_argument("--layout", choices=("auto", "ys930", "ys925"), default="auto")
    args = parser.parse_args(argv)
    document = extract_embedded_text(args.pdf)
    layout = detect_layout(document) if args.layout == "auto" else args.layout
    parsed = parse_contacts(document, layout)
    diagnostics = validate(document, layout, parsed)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(record.as_csv_row() for record in parsed.records)
    if args.diagnostics:
        args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostics.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(diagnostics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
