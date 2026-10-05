# Route Builder

Local prototype for turning a CSV of addresses into a volunteer-friendly driving route.

## Contact-table PDF parser

The separate local `contact-table-csv` command converts supported canvass PDFs
to a contact CSV for organizer review. Install the optional PDF reader with
`.venv/bin/python -m pip install -e '.[contacts]'`. For the usual case, run the
one-argument command from the project folder:

```bash
./parse-contact-pdf YS930.pdf
```

The command looks for a bare filename in the current folder, WSL Downloads,
then the matching Windows user's Downloads. You can also give a full PDF path.
It writes `YS930_contacts.csv` and `YS930_contacts_validation.json` beside the
PDF and refuses to overwrite either existing output. Replace `YS930.pdf` with
the new filename. For an inspection-only run or custom output paths, use:

```bash
.venv/bin/python -m route_builder.contacts.cli /path/to/YS930.pdf \
  --output /path/to/YS930_contacts.csv \
  --diagnostics /path/to/YS930_contacts_validation.json
```

Omit `--output` to inspect and validate without writing a contact file.
The CSV has `Name,Address,Phone,Turf,Precinct,Town,Street` in that order. YS930
populates the three group-header fields and leaves Turf blank; YS925 populates
Turf and leaves the three group-header fields blank. Source row order, shared
addresses, unit text, leading zeroes, and missing phone fields are preserved.
The command uses embedded PDF text and positional rows; it does not contact an
external service. Scanned PDFs and other layouts require inspection and a new
adapter. See [the parser handoff](docs/CONTACT_TABLE_PARSER.md) for verified
layouts, checks, and limitations. Keep real PDFs, contact CSVs, and extracted
text out of Git.

The project is intentionally small. See:
- `AGENTS.md` for implementation constraints.
- `docs/PROJECT_SPEC.md` for the complete MVP specification.
- `docs/WINDOWS_ORGANIZER.md` for Windows installation and organizer instructions.
- `sample_data/organizer_template.csv` for the required `id,address` format.
- `sample_data/addresses.csv` for the initial user-supplied input (currently malformed CSV).
- `sample_data/route_addresses` for the same addresses with valid CSV quoting.
- `sample_data/demo_coordinates.json` for deterministic placeholder coordinates.

## Organizer command

Create one CSV per route with the exact `id,address` header. Quote addresses containing commas; start from `sample_data/organizer_template.csv`. After installing the project (see the Windows guide or the Python setup below), run:

```bash
.venv/bin/python -m route_builder.cli prepare my_addresses.csv --name "North Route" --output build/routes
```

The first run creates `build/routes/North-Route/validation.csv`, `census_comparison.csv`, and `geocode_review.html`. Inspect every match and pin. Correct the CSV and rerun if needed. Once reviewed, run the same command with `--reviewed`:

```bash
.venv/bin/python -m route_builder.cli prepare my_addresses.csv --name "North Route" --output build/routes --reviewed
```

This writes `build/routes/North-Route/North-Route.html` and `route.csv`. The HTML is the only file volunteers need. The builder refuses to overwrite an existing named volunteer file; use a new name for a revised route. Public geocoding and routing endpoints are intended for small prototype runs, and their responses are cached locally.

## Milestone 1 demo

Python 3.11+ is required. From this repository:

```bash
PYTHONPATH=src python3 -m route_builder.cli build sample_data/route_addresses \
  --fixture sample_data/demo_coordinates.json --output build
```

Open `build/route.html` on a phone or desktop browser. The HTML is self-contained and stores progress in browser localStorage. It asks for device location to choose the closest stop in the supplied order; if location is unavailable, the volunteer can choose any first stop from the list. The location is not stored. The navigation choice and Done, Skip, Undo, and skipped-stop revisit progress persist on that device.

**The fixture coordinates are fabricated. Navigation links are functional but lead to those placeholders. Do not distribute this file for real deliveries.** The CSV order is treated as the canonical loop for this demo.

## Geocoding review

The local `validate` command can query a Nominatim-compatible search endpoint and write `build/validation.csv` plus a reusable `build/geocode_cache.json`. It preserves source addresses and labels matches READY, REVIEW, or FAILED. If the exact query fails, it tries a small set of formatting changes and flags any resulting match for review. READY means a unique candidate has matching house number, street, and postal code; the organizer still needs to inspect it. This report is **not** fed into the volunteer page automatically.

For the public OpenStreetMap Nominatim server, read its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) before using it. This local prototype sends one request at a time, waits at least 1.1 seconds between requests, caches results, and requires an identifying User-Agent. Public Nominatim is suited only to small, occasional runs; use a different provider for sustained or larger workloads. Geocoding data © OpenStreetMap contributors.

```bash
PYTHONPATH=src python3 -m route_builder.cli validate sample_data/route_addresses \
  --endpoint https://nominatim.openstreetmap.org/search \
  --user-agent 'RouteBuilderLocal/0.1 (+https://github.com/bltconsulting/route-builder)' \
  --output build
PYTHONPATH=src python3 -m route_builder.cli review-map build/validation.csv \
  --output build/geocode_review.html
```

The review map is a portable coordinate diagram with links to inspect each pin on OpenStreetMap or Google Maps. It does not use external map tiles inside the file; opening a pin link requires internet access.

## Census Geocoder comparison

The Census Geocoder provides a second, independent result for U.S. street addresses. This local command caches its responses and writes `build/census_comparison.csv` with both providers' coordinates and their separation:

```bash
PYTHONPATH=src python3 -m route_builder.cli compare-census sample_data/route_addresses \
  --validation build/validation.csv --output build
```

Census coordinates are interpolated along street address ranges, so a full address match is useful evidence but may not point to a business entrance or building. Large differences between providers call for map review. The comparison report does not change the volunteer route.

For a **test-only** volunteer route using uniquely matched Census coordinates, run:

```bash
PYTHONPATH=src python3 -m route_builder.cli build sample_data/grand_blanc_addresses.csv \
  --census-comparison build/grand_blanc/census_comparison.csv \
  --output build/grand_blanc
```

The page displays a prominent estimated-coordinate warning and retains the supplied CSV order. Review address spellings, duplicates, and destination pins before driving or sharing it.

## Road routing test

From a fresh checkout, install the project in a local Python 3.11+ environment, validate the test addresses, compare them with Census results, then build a driving-time matrix and optimize a closed loop. The geocoding and matrix steps contact public services; review `validation.csv` and `census_comparison.csv` before using their coordinates.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m route_builder.cli validate sample_data/grand_blanc_addresses.csv \
  --endpoint https://nominatim.openstreetmap.org/search \
  --user-agent 'RouteBuilderLocal/0.1 (+https://github.com/bltconsulting/route-builder)' \
  --output build/grand_blanc
.venv/bin/python -m route_builder.cli compare-census sample_data/grand_blanc_addresses.csv \
  --validation build/grand_blanc/validation.csv --output build/grand_blanc
.venv/bin/python -m route_builder.cli review-map build/grand_blanc/validation.csv \
  --output build/grand_blanc/geocode_review.html
.venv/bin/python -m route_builder.cli optimize sample_data/grand_blanc_addresses.csv \
  --census-comparison build/grand_blanc/census_comparison.csv \
  --matrix-endpoint https://router.project-osrm.org \
  --output build/grand_blanc/optimized
```

The routing command writes `route.csv`, a self-contained `route.html`, and a reusable driving-matrix cache. The CSV includes each leg's modeled driving time and distance; its final `next_id` returns to the first stop. The volunteer page rotates this fixed loop to the chosen starting stop. OSRM's public demo server is suitable only for a small prototype request; the cached matrix avoids repeat requests. This test route uses estimated Census coordinates, so inspect its destination pins before driving or sharing it. Stops 13 and 14 share an address and remain separate records in this test; duplicate collapsing is not yet implemented.

## Multiple routes from one address list

Start with an `id,address` CSV, run the existing validation and Census comparison
steps, and review every destination pin. Then request the number of routes:

```bash
.venv/bin/python -m route_builder.cli plan-routes my_addresses.csv \
  --census-comparison build/reviewed/census_comparison.csv \
  --routes 7 --output build/seven_routes
```

`build/seven_routes/routes.csv` has one row per input stop, sorted by
`route_number` then `stop_number`. It retains the original `id` and source
address, matched address, coordinates, the next stop in each closed loop, and
modeled driving time/distance for that leg. Its `review_note` flags street-name
differences from Census, duplicate source addresses, and coincident estimated
coordinates. `route_summary.csv` reports stops, modeled loop distance and
driving time, and flagged-stop count for each group. Geographic grouping balances stop
counts to within one stop per route; each group then gets its own road-driving
matrix and optimized closed loop. The algorithm balances counts, not volunteer
work hours or driving time. Route numbers are arbitrary labels, and each loop's
Stop 1 is a fixed rotation rather than a chosen depot. Review the groups and
pins before sharing, especially because Census coordinates are estimates. This
command exports a planning CSV; it does not yet create separate volunteer HTML
files for the groups. It refuses to overwrite an existing `routes.csv`.

To hand out a route, copy only the reviewed `build/grand_blanc/optimized/route.html` file to each volunteer. Their chosen navigation app and progress are saved in that browser on that device. The file does not sync progress across devices, and regenerating a route with changed stops can start a new progress record. The `build/` directory is ignored by Git, so a fresh checkout must run the commands again.

The parser rejects `sample_data/addresses.csv` because its addresses contain unquoted commas. It reports the CSV line to fix. Both original files remain untouched.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_route_state.cjs
```

OR-Tools is the routing dependency. Node is only used to test the JavaScript state transitions.
