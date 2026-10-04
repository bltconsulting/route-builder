# Contact-table parser handoff

`src/route_builder/contacts/` contains a shared seven-column record schema, local
PDF text/position extraction, layout adapters, validation, and CSV export.
Install the optional `contacts` dependency and use the command in `README.md`.
The adapters reject an unsupported layout, missing/ambiguous row pair, address
that conflicts with its Street header, or a printed people-total mismatch.
Validation JSON is separate from the contact CSV and contains aggregate counts
only. No document content is executed or sent to a service.

## Verified YS930 layout (September 30, 2026)

- `YS930.pdf` has 11 PDF pages. Pages 1–2 are script/cover material; contact
  rows are on pages 3–11. Embedded text is present, so OCR was unnecessary.
- Each gray bar is a three-part header separated by middle dots: complete
  precinct label, town, street. The parser splits on middle dots, preserving
  hyphens and leading zeros in the precinct label. A header applies until the
  next header, including across a page break. A repeated continuation header
  updates metadata but does not create a contact.
- Contact rows use aligned columns: address at the left, name to its right,
  with the phone (when printed) on the following detail line beneath the name.
  Positional pairing prevents the next person's phone from filling a blank.
- The address column already contains the full street address on every row;
  two addresses include printed apartment text. No YS930 address needed
  assembly. If a future row contains only a house number and optional unit,
  this adapter appends the current Street header exactly once. A conflicting
  full street address causes an error instead of a guess.
- No turf number is printed as YS930 contact metadata. The Turf column is blank.
  Precinct numbers are never used as turf numbers.

Validation against the actual PDF: 170 people extracted, matching the printed
**People: 170**. The printed **Doors: 162** is a household/door count, not the
contact count. The output has 115 group headers, 7 blank phones where the
source has no phone, 8 addresses shared by multiple people, and 0 assembled
addresses. Page contact counts are 21, 22, 20, 20, 20, 21, 22, 20, and 4.
The group header carries onto pages 4, 5, and 11 before the next gray bar.
Representative first, middle, continuation, and final pages were inspected
against rendered images. All 170 address/name positions paired uniquely and
all complete addresses matched their current Street header. No unresolved
field ambiguity remains in this file.

## YS925 regression adapter

`YS925.pdf` has a turf summary and separate turf packets, with script pages
between packets. Its contact rows use the same aligned columns but different
gray headings. The adapter carries the latest `Turf NN` packet heading across
contact pages and does not treat street-group bars as precinct metadata.
Reparsing verified all 152 records and exactly matched the earlier organizer
CSV's original `Name,Address,Phone,Turf` values in row order. Per-turf people
counts are 22, 17, 17, 24, 22, 20, 19, 10, and 1. Six source phone fields are
blank. The three new metadata columns remain blank for this format.

## Extension rule

Inspect embedded text, rendered representative pages, page breaks, repeated
headers, row columns, printed people totals, shared households, units, and
missing phones before adding a layout. Keep the adapter specific to the
observed PDF; do not infer precincts from street names or geocoding. For a
scanned PDF, add a local OCR path with image review and explicit uncertainty
reporting before using its output. Never silently deduplicate people.
