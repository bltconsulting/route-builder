"""Strict input handling for the local route prototype."""

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Address:
    id: str
    source_address: str


def read_addresses(path: str | Path) -> list[Address]:
    """Read the two-column CSV without guessing where unquoted commas belong."""
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream, strict=True)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("Address CSV is empty") from exc
        if header != ["id", "address"]:
            raise ValueError("Address CSV header must be exactly: id,address")
        addresses: list[Address] = []
        seen: set[str] = set()
        for row in reader:
            if len(row) != 2:
                raise ValueError(
                    f"CSV line {reader.line_num}: expected 2 columns; quote addresses containing commas"
                )
            stop_id, source_address = row
            if not stop_id.strip() or not source_address.strip():
                raise ValueError(f"CSV line {reader.line_num}: id and address are required")
            if stop_id in seen:
                raise ValueError(f"CSV line {reader.line_num}: duplicate id {stop_id!r}")
            seen.add(stop_id)
            addresses.append(Address(stop_id, source_address))
    if not addresses:
        raise ValueError("Address CSV has no stops")
    return addresses
