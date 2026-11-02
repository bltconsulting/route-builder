"""Shared output record for contact-table adapters."""

from dataclasses import dataclass

CSV_FIELDS = ("Name", "Address", "Phone", "Turf", "Precinct", "Town", "Street")


@dataclass(frozen=True)
class ContactRecord:
    name: str
    address: str
    phone: str = ""
    turf: str = ""
    precinct: str = ""
    town: str = ""
    street: str = ""

    def as_csv_row(self) -> dict[str, str]:
        return dict(zip(CSV_FIELDS, (
            self.name, self.address, self.phone, self.turf,
            self.precinct, self.town, self.street,
        ), strict=True))
