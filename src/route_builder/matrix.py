"""Road travel-cost matrix behind a replaceable OSRM adapter."""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .route import Stop


@dataclass(frozen=True)
class DrivingMatrix:
    durations: list[list[float]]  # seconds
    distances: list[list[float]]  # meters
    snap_distances: list[float]  # meters from supplied point to routed road


def parse_osrm_table(data: dict, count: int) -> DrivingMatrix:
    if data.get("code") != "Ok":
        raise ValueError(f"OSRM table failed: {data.get('code', 'unknown error')}")
    tables = []
    for name in ("durations", "distances"):
        table = data.get(name)
        if not isinstance(table, list) or len(table) != count:
            raise ValueError(f"OSRM {name} matrix has the wrong size")
        checked = []
        for row in table:
            if not isinstance(row, list) or len(row) != count:
                raise ValueError(f"OSRM {name} matrix has the wrong size")
            if any(value is None or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in row):
                raise ValueError(f"OSRM {name} matrix contains an unreachable or invalid leg")
            checked.append([float(value) for value in row])
        tables.append(checked)
    sources = data.get("sources")
    if not isinstance(sources, list) or len(sources) != count:
        raise ValueError("OSRM returned incomplete source waypoints")
    snaps = []
    for source in sources:
        distance = source.get("distance") if isinstance(source, dict) else None
        if not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance < 0:
            raise ValueError("OSRM returned an invalid road snap distance")
        snaps.append(float(distance))
    return DrivingMatrix(tables[0], tables[1], snaps)


class OsrmMatrixAdapter:
    def __init__(self, base_url: str, cache_path: str | Path):
        if not base_url.startswith("https://"):
            raise ValueError("OSRM endpoint must use HTTPS")
        self.base_url = base_url.rstrip("/")
        self.cache_path = Path(cache_path)

    def table(self, stops: list[Stop]) -> DrivingMatrix:
        if len(stops) < 2:
            raise ValueError("A route needs at least two stops")
        coordinates = ";".join(f"{stop.longitude:.8f},{stop.latitude:.8f}" for stop in stops)
        url = f"{self.base_url}/table/v1/driving/{coordinates}?{urlencode({'annotations': 'duration,distance'})}"
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cache = json.loads(self.cache_path.read_text(encoding="utf-8")) if self.cache_path.exists() else {}
        if cache.get("request_hash") == key:
            data = cache["response"]
        else:
            request = Request(url, headers={"User-Agent": "RouteBuilderLocal/0.1 (+https://github.com/bltconsulting/route-builder)", "Accept": "application/json"})
            with urlopen(request, timeout=45) as response:
                data = json.load(response)
            result = parse_osrm_table(data, len(stops))
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps({"request_hash": key, "response": data}, indent=2), encoding="utf-8")
            return result
        return parse_osrm_table(data, len(stops))
