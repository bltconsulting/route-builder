"""Synthetic contact-table cases; real campaign records never enter the test tree."""

import csv
from pathlib import Path

import pytest

from route_builder.contacts.adapters import detect_layout, parse_contacts
from route_builder.contacts.cli import main
from route_builder.contacts.pdf import ExtractedPDF, TextLine
from route_builder.contacts.quick import main as quick_main
from route_builder.contacts.schema import CSV_FIELDS
from route_builder.contacts.validation import validate


def line(page: int, x: float, y: float, text: str) -> TextLine:
    return TextLine(page, x, y, text)


def contact(page: int, y: float, address: str, name: str, detail: str) -> tuple[TextLine, ...]:
    return (
        line(page, 18, y, address),
        line(page, 290, y, name),
        line(page, 290, y + 8.8, detail),
    )


def synthetic_ys930() -> ExtractedPDF:
    page1 = (line(1, 18, 20, "People: 3"), line(1, 18, 30, "Doors: 2"))
    page2 = (
        line(2, 23, 20, "Example - City - 004 · Sampletown · Oak St"),
        *contact(2, 40, "101 Oak St Apt 2", "Rivera, Alex", "(810) 555-0101 40 F"),
    )
    page3 = (
        *contact(3, 20, "101 Oak St Apt 2", "Rivera, Sam", "41 M"),
        line(3, 23, 50, "Example - City - 005 · Sampletown · Pine Rd"),
        *contact(3, 70, "202", "Taylor, Jo", "(810) 555-0102 55 F"),
    )
    return ExtractedPDF((page1, page2, page3), (
        "People: 3\nDoors: 2", "Example - City - 004 · Sampletown · Oak St", "",
    ))


def synthetic_ysrequests() -> ExtractedPDF:
    return ExtractedPDF(
        (
            (line(1, 18, 20, "People: 2"), line(1, 18, 30, "Doors: 2")),
            (line(2, 18, 20, "Canvass script"),),
            (
                line(3, 23, 20, "Example - City - 003 · 2051 · Amy St · Sampletown"),
                *contact(3, 40, "2051 Amy St", "Rivera, Alex", "(810) 555-0101 40 F"),
                line(3, 23, 70, "Example - City - 004 · 2062 · Morrish St · Sampletown"),
                *contact(3, 90, "2062 Morrish St", "Taylor, Jo", "55 M"),
            ),
        ),
        ("People: 2\nDoors: 2", "Canvass script", ""),
    )


def synthetic_ysparity() -> ExtractedPDF:
    return ExtractedPDF(
        (
            (line(1, 18, 20, "People: 3"), line(1, 18, 30, "Doors: 2")),
            (
                line(2, 23, 20, "Example · Example - Burton City - 004 · Oak St · Odd"),
                *contact(2, 40, "101 Oak St Apt 2", "Rivera, Alex", "(810) 555-0101 40 F"),
            ),
            (
                *contact(3, 20, "101 Oak St Apt 2", "Rivera, Sam", "41 M"),
                line(3, 23, 50, "Example · Example - Burton City - 005 · Pine Rd · Even"),
                *contact(3, 70, "202 Pine Rd", "Taylor, Jo", "(810) 555-0102 55 F"),
            ),
        ),
        ("People: 3\nDoors: 2", "", ""),
    )


def test_ysparity_header_carryover_shared_address_and_town_derivation() -> None:
    document = synthetic_ysparity()
    assert detect_layout(document) == "ysparity"
    parsed = parse_contacts(document, "ysparity")
    report = validate(document, "ysparity", parsed)
    assert [r.address for r in parsed.records] == ["101 Oak St Apt 2", "101 Oak St Apt 2", "202 Pine Rd"]
    assert [r.precinct for r in parsed.records] == [
        "Example - Burton City - 004", "Example - Burton City - 004", "Example - Burton City - 005",
    ]
    assert [r.town for r in parsed.records] == ["Burton City"] * 3
    assert [r.phone for r in parsed.records] == ["(810) 555-0101", "", "(810) 555-0102"]
    assert all(not r.turf for r in parsed.records)
    assert report["printed_people"] == report["extracted_people"] == 3
    assert report["shared_address_count"] == 1
    assert report["page_numbers_with_carried_header"] == (3,)
    assert report["assembled_address_count"] == 0


def test_ysparity_rejects_wrong_side_of_street() -> None:
    document = synthetic_ysparity()
    pages = list(document.pages)
    pages[2] = tuple(
        line(item.page, item.x, item.y, "203 Pine Rd") if item.text == "202 Pine Rd" else item
        for item in pages[2]
    )
    with pytest.raises(ValueError, match="conflicts with Even header"):
        parse_contacts(ExtractedPDF(tuple(pages), document.page_text), "ysparity")


def test_ysrequests_four_part_headers_and_blank_phone() -> None:
    document = synthetic_ysrequests()
    assert detect_layout(document) == "ysrequests"
    parsed = parse_contacts(document, "ysrequests")
    report = validate(document, "ysrequests", parsed)
    assert [r.address for r in parsed.records] == ["2051 Amy St", "2062 Morrish St"]
    assert [r.precinct for r in parsed.records] == ["Example - City - 003", "Example - City - 004"]
    assert [r.town for r in parsed.records] == ["Sampletown", "Sampletown"]
    assert [r.street for r in parsed.records] == ["Amy St", "Morrish St"]
    assert [r.phone for r in parsed.records] == ["(810) 555-0101", ""]
    assert [r.turf for r in parsed.records] == ["", ""]
    assert report["printed_people"] == report["extracted_people"] == 2


def test_ysrequests_rejects_house_number_conflict() -> None:
    document = synthetic_ysrequests()
    pages = list(document.pages)
    pages[2] = tuple(
        line(item.page, item.x, item.y, "2052 Amy St") if item.text == "2051 Amy St" else item
        for item in pages[2]
    )
    with pytest.raises(ValueError, match="house-number header"):
        parse_contacts(ExtractedPDF(tuple(pages), document.page_text), "ysrequests")


def test_ys930_carries_header_keeps_shared_people_and_assembles_house_only() -> None:
    document = synthetic_ys930()
    assert detect_layout(document) == "ys930"
    parsed = parse_contacts(document, "ys930")
    report = validate(document, "ys930", parsed)
    assert len(parsed.records) == 3
    assert [r.address for r in parsed.records] == [
        "101 Oak St Apt 2", "101 Oak St Apt 2", "202 Pine Rd",
    ]
    assert [r.precinct for r in parsed.records] == [
        "Example - City - 004", "Example - City - 004", "Example - City - 005",
    ]
    assert [r.phone for r in parsed.records] == ["(810) 555-0101", "", "(810) 555-0102"]
    assert all(not r.turf for r in parsed.records)
    assert report["shared_address_count"] == 1
    assert report["page_numbers_with_carried_header"] == (3,)
    assert report["assembled_address_count"] == 1


def test_repeated_header_does_not_create_contact() -> None:
    document = synthetic_ys930()
    pages = list(document.pages)
    pages[2] = (line(3, 23, 10, "Example - City - 004 · Sampletown · Oak St"), *pages[2])
    parsed = parse_contacts(ExtractedPDF(tuple(pages), document.page_text), "ys930")
    assert len(parsed.records) == 3
    assert parsed.header_count == 3
    assert parsed.carried_pages == ()


def test_conflicting_address_street_fails_loudly() -> None:
    document = synthetic_ys930()
    pages = list(document.pages)
    pages[1] = tuple(
        line(item.page, item.x, item.y, "101 Maple Dr") if item.text == "101 Oak St Apt 2" else item
        for item in pages[1]
    )
    with pytest.raises(ValueError, match="does not match current street"):
        parse_contacts(ExtractedPDF(tuple(pages), document.page_text), "ys930")


def test_missing_or_misaligned_name_fails_instead_of_pairing_next_row() -> None:
    document = synthetic_ys930()
    pages = list(document.pages)
    pages[1] = tuple(item for item in pages[1] if item.text != "Rivera, Alex")
    with pytest.raises(ValueError, match="0 paired names"):
        parse_contacts(ExtractedPDF(tuple(pages), document.page_text), "ys930")


def test_ys925_turf_heading_and_people_not_doors() -> None:
    document = ExtractedPDF(
        (
            (line(1, 18, 10, "Turf Packet Summary"),),
            (line(2, 18, 10, "Test Packet Turf 01"), line(2, 239, 10, "2 People / 1 Doors")),
            (*contact(3, 20, "11 First St", "Lee, Pat", "(810) 555-0111"),
             *contact(3, 40, "11 First St", "Lee, Kim", "36 F")),
        ),
        ("Turf Packet Summary\nTurf 01\n2\n1", "", ""),
    )
    parsed = parse_contacts(document, detect_layout(document))
    report = validate(document, "ys925", parsed)
    assert [r.turf for r in parsed.records] == ["Turf 01", "Turf 01"]
    assert report["printed_people"] == 2
    assert report["missing_phone_count"] == 1


def test_schema_starts_with_original_columns_and_csv_quotes_names(tmp_path: Path) -> None:
    assert CSV_FIELDS[:4] == ("Name", "Address", "Phone", "Turf")
    record = parse_contacts(synthetic_ys930(), "ys930").records[0]
    path = tmp_path / "contacts.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow(record.as_csv_row())
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.DictReader(stream))[0]["Name"] == "Rivera, Alex"


def test_one_argument_command_names_outputs_and_protects_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "New List.pdf"
    pdf.touch()
    calls: list[list[str]] = []
    monkeypatch.setattr("route_builder.contacts.quick.convert", lambda args: calls.append(args) or 0)
    assert quick_main([str(pdf)]) == 0
    assert calls == [[
        str(pdf), "--output", str(tmp_path / "New List_contacts.csv"),
        "--diagnostics", str(tmp_path / "New List_contacts_validation.json"),
    ]]
    (tmp_path / "New List_contacts.csv").touch()
    with pytest.raises(SystemExit):
        quick_main([str(pdf)])
    assert len(calls) == 1
