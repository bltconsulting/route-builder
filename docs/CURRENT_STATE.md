# Route Builder handoff — October 2026

Branch: `feature/organizer-handoff`. Latest commit at this handoff:
`f57b4f1 Add printable route PDF packets and matched address hints`.

The project has a Python CLI for contact PDF parsing, address validation and
comparison, multi-route planning, offline printable route maps, PDF route
overviews, and self-contained volunteer navigation HTML. The volunteer HTML
keeps route progress locally and sends one destination at a time to a selected
navigation app. See `README.md`, `docs/PROJECT_SPEC.md`, and
`docs/WINDOWS_ORGANIZER.md` for workflow and constraints.

The recent seven-route example uses 66 stops from the organizer's v3 CSV. Its
planned-route CSV is at
`build/route_test_20261004_v3/seven_routes/routes.csv`. The generated packet
is at `build/route_test_20261004_v3/route_packets/` and was copied to Windows
Downloads as `route_test_20261004_v3_route_packets/`. The packet contains one
seven-page master PDF, seven individual route PDF overviews, and seven paired
navigation HTML files. Generated outputs and real contact data are ignored by
Git and are not backed up by the code commits.

PDF and HTML route overviews show source addresses without source IDs. When a
route row says the street differs from the Census match, they also show the
matched address as `Possible actual address: ...`. Numbered map pins and stop
order are based on estimated Census coordinates. The map's dashed connectors
indicate stop sequence, not a road-driving path. Flagged addresses and pins
still require organizer review before distribution. The current v3 routes are
uneven in estimated workload; changing that requires a new planning pass, not
just reprinting the packet.

To regenerate PDFs from a reviewed `routes.csv`, install `.[maps]` in the
Python environment and run `route-builder route-pdfs ROUTES_CSV --roads-zip
COUNTY_ROADS_ZIP --output OUTPUT_DIR`. Then run `route-builder volunteer-pages
ROUTES_CSV --output OUTPUT_DIR`. Use a new output directory; the commands do
not overwrite existing files. The known roads ZIP for the example is
`build/map_data/tl_2025_26049_roads.zip`.

Verification at handoff: `python -m pytest -q` passed 37 tests and 4 subtests;
`node --test tests/test_route_state.cjs` passed. The example packet's 15 files
were hash-verified after copying to Windows Downloads.
