"""Offline printable route sheets over Census TIGER/Line road centerlines."""

import csv
import html
import math
import struct
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from .address_review import possible_actual_address


@dataclass(frozen=True)
class Road:
    name: str
    kind: str
    parts: tuple[tuple[tuple[float, float], ...], ...]  # longitude, latitude


def read_tiger_roads(zip_path: str | Path) -> list[Road]:
    """Read the PolyLine and DBF fields used by a county TIGER/Line roads ZIP."""
    with ZipFile(zip_path) as archive:
        shp_name = next((name for name in archive.namelist() if name.lower().endswith(".shp")), None)
        dbf_name = next((name for name in archive.namelist() if name.lower().endswith(".dbf")), None)
        if not shp_name or not dbf_name:
            raise ValueError("Road ZIP must contain .shp and .dbf files")
        shp = archive.read(shp_name)
        dbf = archive.read(dbf_name)
    if len(shp) < 100 or struct.unpack_from(">I", shp)[0] != 9994:
        raise ValueError("Invalid TIGER/Line shapefile")
    dbf_count = struct.unpack_from("<I", dbf, 4)[0]
    header_size, record_size = struct.unpack_from("<HH", dbf, 8)
    fields = []
    offset = 1
    for position in range(32, header_size - 1, 32):
        descriptor = dbf[position:position + 32]
        if not descriptor or descriptor[0] == 13:
            break
        name = descriptor[:11].split(b"\0", 1)[0].decode("ascii")
        length = descriptor[16]
        fields.append((name, offset, length))
        offset += length
    if not {"FULLNAME", "MTFCC"}.issubset({name for name, _, _ in fields}):
        raise ValueError("Road DBF lacks FULLNAME or MTFCC")
    roads = []
    position = 100
    record_number = 0
    while position < len(shp):
        if position + 8 > len(shp):
            raise ValueError("Truncated shapefile record")
        length = struct.unpack_from(">I", shp, position + 4)[0] * 2
        record = shp[position + 8:position + 8 + length]
        position += 8 + length
        if len(record) != length or record_number >= dbf_count:
            raise ValueError("Shapefile and DBF records do not align")
        dbf_row = dbf[header_size + record_number * record_size:
                      header_size + (record_number + 1) * record_size]
        record_number += 1
        if len(dbf_row) != record_size or dbf_row[:1] == b"*":
            continue
        shape_type = struct.unpack_from("<I", record)[0]
        if shape_type == 0:
            continue
        if shape_type != 3:
            raise ValueError(f"Expected road PolyLine shape, got {shape_type}")
        part_count, point_count = struct.unpack_from("<II", record, 36)
        indices = struct.unpack_from(f"<{part_count}I", record, 44)
        point_start = 44 + 4 * part_count
        if point_start + 16 * point_count > len(record):
            raise ValueError("Truncated road PolyLine")
        points = [struct.unpack_from("<dd", record, point_start + 16 * i)
                  for i in range(point_count)]
        parts = tuple(tuple(points[start:end]) for start, end in
                      zip(indices, (*indices[1:], point_count)))
        attributes = {name: dbf_row[start:start + size].decode("latin-1").strip()
                      for name, start, size in fields if name in {"FULLNAME", "MTFCC"}}
        roads.append(Road(attributes["FULLNAME"], attributes["MTFCC"], parts))
    if record_number != dbf_count:
        raise ValueError("Shapefile and DBF record counts differ")
    return roads


def read_routes(csv_path: str | Path) -> dict[int, list[dict[str, str]]]:
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    required = {"route_number", "stop_number", "id", "source_address", "latitude", "longitude", "review_note"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Expected a nonempty plan-routes CSV with coordinates")
    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        route = int(row["route_number"])
        latitude, longitude = float(row["latitude"]), float(row["longitude"])
        if route < 1 or not (math.isfinite(latitude) and math.isfinite(longitude)):
            raise ValueError("Route CSV contains an invalid route or coordinate")
        groups[route].append(row)
    for group in groups.values():
        group.sort(key=lambda row: int(row["stop_number"]))
        if [int(row["stop_number"]) for row in group] != list(range(1, len(group) + 1)):
            raise ValueError("Stop numbers must be consecutive within each route")
    return dict(sorted(groups.items()))


def route_svg(stops: list[dict[str, str]], roads: list[Road]) -> str:
    """Draw roads and numbered pins in a shared local kilometer projection."""
    width, height = 1100, 690
    latitude0 = sum(float(stop["latitude"]) for stop in stops) / len(stops)
    cosine = math.cos(math.radians(latitude0))

    def project(longitude: float, latitude: float) -> tuple[float, float]:
        return longitude * cosine * 111.32, latitude * 111.32

    locations = [project(float(stop["longitude"]), float(stop["latitude"])) for stop in stops]
    center_x = (min(x for x, _ in locations) + max(x for x, _ in locations)) / 2
    center_y = (min(y for _, y in locations) + max(y for _, y in locations)) / 2
    span_x = max(max(x for x, _ in locations) - min(x for x, _ in locations), 0.8) * 1.35
    span_y = max(max(y for _, y in locations) - min(y for _, y in locations), 0.6) * 1.35
    span = max(span_x / width, span_y / height)
    span_x, span_y = span * width, span * height
    bounds = (center_x - span_x / 2, center_y - span_y / 2,
              center_x + span_x / 2, center_y + span_y / 2)

    def pixel(point: tuple[float, float]) -> tuple[float, float]:
        return ((point[0] - bounds[0]) / span_x * width,
                (bounds[3] - point[1]) / span_y * height)

    road_paths = []
    labels = []
    named = set()
    for road in roads:
        for part in road.parts:
            coords = [project(lon, lat) for lon, lat in part]
            if len(coords) < 2 or max(x for x, _ in coords) < bounds[0] or min(x for x, _ in coords) > bounds[2] or max(y for _, y in coords) < bounds[1] or min(y for _, y in coords) > bounds[3]:
                continue
            points = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(pixel, coords))
            css = "major" if road.kind in {"S1100", "S1200"} else "local"
            color, thickness = ("#aeb9c1", 4) if css == "major" else ("#d2d7d6", 2)
            road_paths.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{thickness}"/>')
            if road.name and road.name not in named and css == "major":
                x, y = pixel(coords[len(coords) // 2])
                if 20 < x < width - 20 and 20 < y < height - 20:
                    labels.append(f'<text x="{x:.1f}" y="{y:.1f}" fill="#59636d" font-size="10" stroke="white" stroke-width="2" paint-order="stroke">{html.escape(road.name)}</text>')
                    named.add(road.name)
    pixels = [pixel(location) for location in locations]
    connector = " ".join(f"{x:.1f},{y:.1f}" for x, y in (*pixels, pixels[0]))
    parents = list(range(len(stops)))

    def root(index: int) -> int:
        while parents[index] != index:
            index = parents[index]
        return index

    for i, (x1, y1) in enumerate(pixels):
        for j, (x2, y2) in enumerate(pixels[:i]):
            if math.hypot(x1 - x2, y1 - y2) < 32:
                parents[root(i)] = root(j)
    nearby: dict[int, list[int]] = defaultdict(list)
    for index in range(len(stops)):
        nearby[root(index)].append(index)
    markers = []
    for index, stop in enumerate(stops):
        x, y = pixels[index]
        siblings = nearby[root(index)]
        if len(siblings) > 1:
            angle = 2 * math.pi * siblings.index(index) / len(siblings)
            radius = 20 if len(siblings) == 2 else 25
            new_x, new_y = x + radius * math.cos(angle), y + radius * math.sin(angle)
            markers.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{new_x:.1f}" y2="{new_y:.1f}" stroke="#27486a" stroke-width="2"/>')
            x, y = new_x, new_y
        border, border_width = ("#c22", 4) if stop["review_note"] else ("white", 2)
        label = html.escape(f"Stop {stop['stop_number']} · {stop['source_address']}")
        markers.append(f'<g><title>{label}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="#164b8a" stroke="{border}" stroke-width="{border_width}"/><text x="{x:.1f}" y="{y + 4:.1f}" fill="white" font-size="12" font-weight="700" text-anchor="middle">{html.escape(stop["stop_number"])}</text></g>')
    scale_km = next((size for size in (10, 5, 2, 1, 0.5, 0.2, 0.1)
                     if size / span_x * width < 180), 0.1)
    scale_px = scale_km / span_x * width
    return f'''<svg viewBox="0 0 {width} {height}" role="img" aria-label="Road map with numbered route stops">
<rect width="{width}" height="{height}" fill="#f8faf7"/>
<g>{''.join(road_paths)}</g><g>{''.join(labels)}</g>
<polyline points="{connector}" fill="none" stroke="#d97515" stroke-width="2" stroke-dasharray="6 5" opacity=".85"/><g>{''.join(markers)}</g>
<g><rect x="12" y="{height - 47}" width="{scale_px + 24:.1f}" height="35" rx="5" fill="white" opacity=".9"/><line x1="24" y1="{height - 24}" x2="{24 + scale_px:.1f}" y2="{height - 24}" stroke="#111" stroke-width="3"/><text x="24" y="{height - 30}" font-size="12">{scale_km:g} km</text></g><text x="{width - 42}" y="30" font-size="19" font-weight="700">N ↑</text>
</svg>'''


def generate_printable_maps(groups: dict[int, list[dict[str, str]]], roads: list[Road]) -> str:
    sections = []
    for route, stops in groups.items():
        flagged = sum(bool(stop["review_note"]) for stop in stops)
        items = []
        for stop in stops:
            note = f' <span class="warning">⚠ {html.escape(stop["review_note"])}</span>' if stop["review_note"] else ""
            possible = possible_actual_address(stop)
            hint = f' <span class="warning">Possible actual address: {html.escape(possible)}</span>' if possible else ""
            items.append(f'<li><strong>{html.escape(stop["stop_number"])}.</strong> {html.escape(stop["source_address"])}{note}{hint}</li>')
        sections.append(f'''<section id="route-{route}"><header><h2>Route {route}</h2><p>{len(stops)} stops · {flagged} address review notes · planning draft</p></header>
<div class="sheet"><div class="map">{route_svg(stops, roads)}</div><ol>{''.join(items)}</ol></div>
<footer>Roads: U.S. Census Bureau 2025 TIGER/Line, Genesee County. Pins: estimated Census Geocoder coordinates. Dashed lines show stop order, not the driving path. Verify flagged addresses and pins before use.</footer></section>''')
    links = " · ".join(f'<a href="#route-{route}">Route {route}</a>' for route in groups)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Printable route maps</title>
<style>body{{font:14px system-ui,sans-serif;color:#18222d;background:#eef2f5;margin:0}}main{{max-width:1400px;margin:auto;padding:16px}}nav{{margin:8px 0 16px}}a{{color:#164b8a}}section{{background:white;margin:0 0 24px;padding:16px;break-after:page;box-shadow:0 2px 8px #0002}}header{{display:flex;align-items:baseline;gap:20px}}h2{{margin:0}}.sheet{{display:grid;grid-template-columns:minmax(0,3fr) minmax(250px,1fr);gap:12px}}.map{{min-width:0;border:1px solid #aaa}}svg{{width:100%;height:auto;display:block}}.local{{fill:none;stroke:#d2d7d6;stroke-width:2}}.major{{fill:none;stroke:#aeb9c1;stroke-width:4}}.street{{font-size:10px;fill:#59636d;paint-order:stroke;stroke:#fff;stroke-width:3px}}.sequence{{fill:none;stroke:#d97515;stroke-width:2;stroke-dasharray:6 5;opacity:.85}}.leader{{stroke:#27486a;stroke-width:2}}.pin{{fill:#164b8a;stroke:#fff;stroke-width:2}}.pin.flagged{{stroke:#c22;stroke-width:4}}.pin-label{{fill:white;font-size:12px;font-weight:700;text-anchor:middle}}.scale text{{font-size:12px}}.north{{font-weight:700;font-size:19px}}ol{{list-style:none;padding:0;margin:0;columns:1}}li{{padding:5px 2px;border-bottom:1px solid #ddd;break-inside:avoid}}small{{color:#555}}.warning{{display:block;color:#a31515;font-size:11px}}footer{{margin-top:8px;font-size:11px;color:#555}}@page{{size:letter landscape;margin:.25in}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}nav,h1{{display:none}}section{{margin:0;padding:0;box-shadow:none;min-height:7.9in}}.sheet{{grid-template-columns:minmax(0,3fr) minmax(220px,1fr)}}}}</style></head><body><main><h1>Printable route maps · planning draft</h1><nav>{links}</nav>{''.join(sections)}</main></body></html>'''


def write_printable_maps(routes_csv: str | Path, roads_zip: str | Path,
                         output_html: str | Path) -> Path:
    target = Path(output_html)
    if target.exists():
        raise ValueError(f"{target} already exists; choose a new output filename")
    groups = read_routes(routes_csv)
    roads = read_tiger_roads(roads_zip)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_printable_maps(groups, roads), encoding="utf-8")
    return target
