# Route Builder — MVP Project Specification

## 1. Purpose
Create a lightweight route-building tool for volunteer drivers, with special attention to users who may be uncomfortable with complicated mobile software.

The organizer starts with a CSV of addresses. The pipeline produces:
1. a validation/geocoding report,
2. an optimized route CSV,
3. an interactive organizer QA map,
4. a self-contained volunteer route HTML file.

The volunteer should never need to import a CSV, understand route optimization, create an account, or learn a new navigation application.

## 2. Core design principle
Complexity belongs on the organizer/build side. The volunteer side should be nearly self-explanatory.

Target interaction after first-time setup:

`NAVIGATE → arrive → DONE → NAVIGATE → arrive → DONE`

SKIP and UNDO are available but secondary.

## 3. Input
Initial CSV schema:

```csv
id,address
01,"410 E. Grand Blanc Rd., Grand Blanc, MI 48439"
02,"11225 S Saginaw St, Grand Blanc, MI 48439"
```

Requirements:
- `id` is retained as a stable organizer reference.
- `address` is retained exactly as supplied.
- Later versions may accept optional name/notes fields, but they are not required for MVP.
- The eventual organizer CSV may use different column names or structure. Once a representative file is available, add an explicit import mapping and validation for that format. Do not guess or silently combine malformed columns.

## 4. Geocoding and validation
For each address, obtain:
- latitude
- longitude
- normalized/matched address
- provider metadata useful for assessing the match

Do not silently route questionable results.

Classify each row into a simple organizer-facing status such as:
- READY
- REVIEW
- FAILED

The initial prototype may use an OpenStreetMap-based geocoder. Respect provider usage policies and rate limits. Keep the geocoder behind an adapter so it can later be replaced by another provider without changing the rest of the pipeline.

## 5. Routing matrix
Build a road-driving cost matrix between geocoded stops. Prefer driving time as the optimization cost; retain distance when available.

For prototyping, an OpenStreetMap-based routing service such as OSRM/openrouteservice may be used. Isolate provider-specific code.

## 6. Optimization
Use Google OR-Tools.

For a single assigned group of stops:
- solve a closed-loop Traveling Salesman Problem;
- produce one optimized cyclic ordering;
- preserve the ordering as the canonical/master loop.

Important: the canonical route is a cycle, not a route tied to a volunteer's home.

## 7. Starting-point rotation
At volunteer start:
- request the device's current location;
- select an appropriate entry stop into the canonical loop;
- rotate the loop so that stop becomes Stop 1;
- preserve the optimized cyclic order thereafter.

MVP may select the nearest stop by straight-line/Haversine distance.

Example canonical loop:

`A → B → C → D → E → F → A`

Volunteer starts closest to D:

`D → E → F → A → B → C`

The volunteer's home/current location does not need to be sent to or retained by the organizer.

Fallback:
- provide a simple way to enter a starting address if location permission is unavailable/denied. This can be deferred if it materially complicates Milestone 1.

## 8. Volunteer HTML
Generate a self-contained mobile-first HTML file.

### First use
Show:
- START MY ROUTE
- navigation app choice: Waze / Google Maps / Apple Maps

Remember the navigation app locally.

### Active route
Display approximately:

`Stop 7 of 24 • 17 remaining • 2 skipped`

Then:
- next-stop address
- large NAVIGATE button
- large DONE — NEXT STOP button
- smaller SKIP THIS STOP
- smaller UNDO

### Persistence
Use localStorage for MVP.
Persist:
- selected navigation app
- rotated route/order
- current position
- completed stops
- skipped stops
- enough history to undo the most recent state-changing action

Closing/reopening the page should resume the route.

### Skipped stops
During the primary route, Skip moves the stop to a skipped queue and immediately continues.

When all non-skipped stops are complete:
- show count of skipped stops;
- offer REVISIT SKIPPED STOPS;
- offer FINISH ROUTE.

For MVP, revisiting skipped stops may use their existing relative order. Re-optimization of skipped stops can be a later enhancement.

## 9. Navigation handoff
Send one destination at a time.

Use coordinates rather than asking navigation apps to geocode the address again.

Support:
- Waze
- Google Maps
- Apple Maps

The selected navigation app handles actual driving navigation and rerouting.

## 10. Organizer outputs

### `validation.csv`
Suggested columns:
- id
- source_address
- matched_address
- latitude
- longitude
- status
- notes

### `route.csv`
Suggested columns:
- sequence
- id
- source_address
- matched_address
- latitude
- longitude
- leg_distance
- leg_duration

### `route_map.html`
Interactive QA map showing:
- numbered stops
- route order
- enough address information to detect obvious bad geocodes

### `route.html`
Self-contained volunteer interface.

## 11. Proposed Python dependencies
Initial dependencies:
- pandas
- requests
- ortools
- jinja2
- folium

Optional:
- geopy

Keep the dependency list small.

## 12. Suggested package structure
```text
src/route_builder/
    cli.py
    models.py
    geocode.py
    matrix.py
    optimize.py
    generate.py
    geo.py
templates/
    volunteer_route.html
tests/
sample_data/
```

## 13. CLI direction
A future command should be approximately:

```bash
route-builder build sample_data/addresses.csv --output build/
```

Expected outputs:

```text
build/
    validation.csv
    route.csv
    route_map.html
    route.html
```

A `validate` command may be separated later if useful.

## 14. Milestones

### Milestone 1 — local route UI
- Parse CSV.
- Use fixture coordinates rather than live geocoding.
- Implement canonical-loop rotation from a supplied/current coordinate.
- Generate volunteer HTML.
- Implement navigation-app selection.
- Implement Done / Skip / Undo.
- Persist state.
- Implement skipped-stop completion screen.
- Add automated tests for state/rotation logic.

This proves the volunteer workflow without external-service uncertainty.

### Milestone 2 — geocoding
- Add real geocoding adapter.
- Generate validation report.
- Flag ambiguous/failed addresses.
- Add caching to avoid unnecessary repeated geocoding.

### Milestone 3 — road matrix + optimization
- Add routing matrix adapter.
- Add OR-Tools closed-loop optimization.
- Produce route.csv.

### Milestone 4 — organizer QA
- Generate numbered Folium map.
- Make suspicious points easy to identify.
- Run the supplied sample addresses end-to-end.

### Milestone 5 — multiple routes
Only after the single-route pipeline is reliable:
- accept an organizer-supplied volunteer count (for example, 2–4 volunteers for 20 stops);
- group nearby stops into reasonably compact, balanced territories before route optimization;
- flag large imbalances or isolated stops for organizer review;
- build and optimize a separate closed loop within each group, preserving each loop as its canonical order;
- generate one volunteer HTML file per group.

Grouping should account for workload as well as geography. Stop count is an initial balance measure; driving time and any known stop service time are better measures when available. The organizer should be able to inspect group assignments before routes are distributed. Do not implement clustering with Milestone 1 fixture coordinates, which are placeholders rather than actual stop locations.

## 15. Explicitly out of scope for MVP
- volunteer accounts
- organizer dashboard
- live volunteer tracking
- cloud database
- server-side progress synchronization
- native Android/iOS app
- real-time reassignment
- messaging
- authentication
- complex analytics

## 16. Acceptance criteria for first useful prototype
A nontechnical user can:
1. open the generated route HTML on a phone;
2. choose a familiar navigation app;
3. start near the closest point on the predetermined route;
4. navigate to one stop at a time;
5. mark stops Done or Skip;
6. undo an accidental Done/Skip;
7. close and reopen the page without losing progress;
8. finish the main route and optionally revisit skipped stops.

The organizer can inspect the generated route and identify bad address matches before distributing it.
