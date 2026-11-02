"""Address hints shared by organizer sheets and volunteer pages."""


def possible_actual_address(row: dict[str, str]) -> str:
    """Return the Census rewrite only for a flagged address discrepancy."""
    note = row.get("review_note", "").lower()
    if "differs from census match" in note:
        return row.get("matched_address", "").strip()
    return ""
