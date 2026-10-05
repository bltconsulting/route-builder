"""Small synthetic TIGER road file and printable route rendering."""

import csv
import struct
from pathlib import Path
from zipfile import ZipFile

from route_builder.printable_maps import read_tiger_roads, write_printable_maps


def road_zip(path: Path) -> None:
    content = bytearray(80)
    struct.pack_into("<I", content, 0, 3)
    struct.pack_into("<4d", content, 4, -83.1, 42.0, -83.0, 42.1)
    struct.pack_into("<II", content, 36, 1, 2)
    struct.pack_into("<I", content, 44, 0)
    struct.pack_into("<4d", content, 48, -83.1, 42.0, -83.0, 42.1)
    shp = bytearray(100)
    struct.pack_into(">I", shp, 0, 9994)
    struct.pack_into(">I", shp, 24, 94)
    struct.pack_into("<II", shp, 28, 1000, 3)
    shp.extend(struct.pack(">II", 1, 40))
    shp.extend(content)

    dbf = bytearray(97)
    dbf[0] = 3
    struct.pack_into("<IHH", dbf, 4, 1, 97, 26)
    for position, name, length in ((32, b"FULLNAME", 20), (64, b"MTFCC", 5)):
        dbf[position:position + len(name)] = name
        dbf[position + 11] = ord("C")
        dbf[position + 16] = length
    dbf[96] = 13
    dbf.extend(b" " + b"Example Rd".ljust(20) + b"S1400")
    with ZipFile(path, "w") as archive:
        archive.writestr("roads.shp", shp)
        archive.writestr("roads.dbf", dbf)


def test_printable_map_has_local_roads_numbered_pins_and_review_note(tmp_path: Path) -> None:
    roads = tmp_path / "roads.zip"
    road_zip(roads)
    parsed = read_tiger_roads(roads)
    assert len(parsed) == 1
    assert parsed[0].name == "Example Rd"
    routes = tmp_path / "routes.csv"
    with routes.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["route_number", "stop_number", "id",
                                                     "source_address", "latitude", "longitude", "review_note"])
        writer.writeheader()
        writer.writerows([
            {"route_number": 1, "stop_number": 1, "id": "a", "source_address": "1 Example Rd",
             "latitude": 42.02, "longitude": -83.08, "review_note": "Street differs"},
            {"route_number": 1, "stop_number": 2, "id": "b", "source_address": "2 Example Rd",
             "latitude": 42.08, "longitude": -83.02, "review_note": ""},
        ])
    target = write_printable_maps(routes, roads, tmp_path / "print.html")
    page = target.read_text(encoding="utf-8")
    assert "Example Rd" in page
    assert 'xlink:href=' not in page and 'tile.openstreetmap.org' not in page
    assert "Route 1" in page and "Street differs" in page
    assert page.count("<circle ") == 2
    assert "size:letter landscape" in page
