"""Offline, letter-size PDF route overviews with one route per page."""

from pathlib import Path

from .address_review import possible_actual_address
from .printable_maps import read_routes, read_tiger_roads, route_svg


def _wrapped(text: str, width: float, font: str, size: float, fitz) -> list[str]:
    lines = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and fitz.get_text_length(candidate, fontname=font, fontsize=size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_route(page, number: int, rows: list[dict[str, str]], roads, fitz) -> None:
    page.insert_text((22, 34), f"Route {number} overview", fontsize=18, fontname="helv", color=(0.08, 0.21, 0.37))
    flagged = sum(bool(row["review_note"]) for row in rows)
    page.insert_text((22, 52), f"{len(rows)} stops  |  {flagged} review notes  |  planning draft", fontsize=9, color=(0.35, 0.39, 0.42))
    svg = fitz.open(stream=route_svg(rows, roads).encode("utf-8"), filetype="svg")
    vector = fitz.open(stream=svg.convert_to_pdf(), filetype="pdf")
    page.show_pdf_page(fitz.Rect(22, 70, 548, 403), vector, 0)
    vector.close()
    svg.close()
    x, y, width = 560, 77, 208
    # Fit the stop list within the page while retaining all review details.
    for size in (9, 8.5, 8, 7.5):
        entries = []
        needed = 0
        for row in rows:
            address = _wrapped(f"{row['stop_number']}. {row['source_address']}", width, "hebo", size, fitz)
            detail = []
            if row["review_note"]:
                detail.extend(_wrapped(row["review_note"], width, "helv", size - 1, fitz))
            possible = possible_actual_address(row)
            if possible:
                detail.extend(_wrapped(f"Possible actual address: {possible}", width, "helv", size - 1, fitz))
            entries.append((address, detail))
            needed += len(address) * (size + 2) + len(detail) * (size + 1) + 6
        if needed <= 480:
            break
    for address, detail in entries:
        for line in address:
            page.insert_text((x, y), line, fontname="hebo", fontsize=size, color=(0.08, 0.21, 0.37))
            y += size + 2
        for line in detail:
            page.insert_text((x, y), line, fontname="helv", fontsize=size - 1, color=(0.65, 0.13, 0.13))
            y += size + 1
        y += 6
    if y > 558:
        raise ValueError(f"Route {number} stop list does not fit on one PDF page")
    page.insert_text((22, 573), "Roads: U.S. Census Bureau 2025 TIGER/Line. Pins: estimated Census Geocoder coordinates.", fontsize=8, color=(0.32, 0.35, 0.38))
    page.insert_text((22, 586), "Dashed lines show stop order, not driving paths. Verify flagged addresses and pins before use.", fontsize=8, color=(0.32, 0.35, 0.38))


def write_route_pdfs(routes_csv: str | Path, roads_zip: str | Path, output_dir: str | Path) -> list[Path]:
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise ImportError("Install route-builder[maps] to generate PDFs") from exc
    groups = read_routes(routes_csv)
    roads = read_tiger_roads(roads_zip)
    folder = Path(output_dir)
    master_path = folder / "Master-Route-Overviews.pdf"
    individual = [folder / f"Route-{number:02d}-Overview.pdf" for number in groups]
    for path in [master_path, *individual]:
        if path.exists():
            raise ValueError(f"{path} already exists; choose a new output folder")
    master = fitz.open()
    documents = []
    try:
        for (number, rows), path in zip(groups.items(), individual):
            doc = fitz.open()
            _draw_route(doc.new_page(width=792, height=612), number, rows, roads, fitz)
            master.insert_pdf(doc)
            documents.append((doc, path))
        folder.mkdir(parents=True, exist_ok=True)
        master.save(master_path)
        for doc, path in documents:
            doc.save(path)
    finally:
        master.close()
        for doc, _ in documents:
            doc.close()
    return [master_path, *individual]
