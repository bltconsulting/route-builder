"""Two-step organizer workflow: inspect geocodes, then build one named route."""

import csv
import hashlib
import json
import re
from pathlib import Path

from .census import CensusGeocoder, compare_csv
from .geocode import NominatimGeocoder, validate_csv
from .input import read_addresses
from .review_map import write_census_review_map
from .routing import build_optimized_route

NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"
OSRM_ENDPOINT = "https://router.project-osrm.org"
USER_AGENT = "RouteBuilderLocal/0.1 (+https://github.com/bltconsulting/route-builder)"
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def route_name(value: str) -> str:
    """Turn a friendly route name into a portable folder and HTML filename."""
    name = re.sub(r"\s+", "-", value.strip())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) or name.upper() in WINDOWS_RESERVED:
        raise ValueError("Route name must contain letters, digits, spaces, hyphens, or underscores")
    return name


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_report_ids(input_csv: Path, report: Path) -> None:
    addresses = read_addresses(input_csv)
    with report.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if [(row.get("id"), row.get("source_address")) for row in rows] != [(address.id, address.source_address) for address in addresses]:
        raise ValueError(f"{report.name} does not match the input CSV; run prepare without --reviewed again")


def prepare_route(input_csv: str | Path, name: str, output_dir: str | Path, *, reviewed: bool = False,
                  geocoder_endpoint: str = NOMINATIM_ENDPOINT, matrix_endpoint: str = OSRM_ENDPOINT,
                  user_agent: str = USER_AGENT) -> Path:
    source = Path(input_csv)
    read_addresses(source)  # Reject malformed CSV before any service requests.
    stem = route_name(name)
    folder = Path(output_dir) / stem
    volunteer_file = folder / f"{stem}.html"
    if volunteer_file.exists():
        raise ValueError(f"{volunteer_file} already exists; choose a new route name to preserve it")
    manifest = folder / "review_input.json"
    validation = folder / "validation.csv"
    comparison = folder / "census_comparison.csv"
    if not reviewed:
        folder.mkdir(parents=True, exist_ok=True)
        manifest.unlink(missing_ok=True)
        geocoder = NominatimGeocoder(geocoder_endpoint, user_agent, folder / "geocode_cache.json")
        validate_csv(source, geocoder, validation)
        census = CensusGeocoder(folder / "census_cache.json")
        compare_csv(source, validation, census, comparison)
        write_census_review_map(comparison, folder / "geocode_review.html")
        manifest.write_text(json.dumps({"input_sha256": _digest(source)}, indent=2), encoding="utf-8")
        return folder
    if not manifest.exists() or not validation.exists() or not comparison.exists():
        raise ValueError("Review files are missing; run prepare without --reviewed first")
    if json.loads(manifest.read_text(encoding="utf-8")).get("input_sha256") != _digest(source):
        raise ValueError("Input CSV changed after the review files were made; run prepare without --reviewed again")
    _check_report_ids(source, validation)
    _check_report_ids(source, comparison)
    build_optimized_route(source, comparison, folder, matrix_endpoint, volunteer_file.name)
    return volunteer_file
