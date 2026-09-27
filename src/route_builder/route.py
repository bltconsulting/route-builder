"""Canonical loop operations; no routing service is involved in Milestone 1."""

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt


@dataclass(frozen=True)
class Stop:
    id: str
    source_address: str
    latitude: float
    longitude: float


def distance_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    lat_delta = radians(b_lat - a_lat)
    lon_delta = radians(b_lon - a_lon)
    arc = sin(lat_delta / 2) ** 2 + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(lon_delta / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(arc))


def rotate_loop(stops: list[Stop], latitude: float, longitude: float) -> list[Stop]:
    if not stops:
        raise ValueError("Cannot rotate an empty route")
    start = min(range(len(stops)), key=lambda i: distance_km(latitude, longitude, stops[i].latitude, stops[i].longitude))
    return stops[start:] + stops[:start]
