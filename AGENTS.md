# AGENTS.md — Route Builder

## Mission
Build a small, reliable route-generation pipeline for nontechnical volunteer drivers.

The organizer supplies a CSV of addresses. The system validates/geocodes them, builds a driving-cost matrix, optimizes a CLOSED LOOP, produces an organizer QA map, and generates a self-contained mobile HTML route.

The volunteer experience must remain deliberately simple.

## MVP constraints
- Python pipeline, not a web application.
- No database, authentication, React, Flask/FastAPI/Django, Docker, cloud infrastructure, or user accounts unless a demonstrated requirement appears.
- Prefer open/free mapping services during prototyping.
- External API/service access must be isolated behind small adapters.
- Never silently accept a questionable geocode. Flag it for organizer review.
- Do not expose API keys in generated volunteer HTML.
- The volunteer's current location should be used locally when possible and should not need to be stored.
- Optimize a closed loop once. At route start, rotate that predetermined loop so the volunteer begins at the most sensible nearby stop. Do not re-solve the whole route on the volunteer's phone for MVP.
- Keep generated volunteer HTML self-contained and usable on a phone.

## Volunteer UX
Initial setup:
1. Open route.
2. Tap START MY ROUTE.
3. Allow location, or enter a starting address as fallback.
4. Choose Waze, Google Maps, or Apple Maps. Remember the choice.

Normal route screen:
- `Stop 7 of 24 • 17 remaining • 2 skipped`
- Next-stop address
- NAVIGATE
- DONE — NEXT STOP
- SKIP THIS STOP
- UNDO

Rules:
- Save progress after every Done, Skip, Undo, or navigation-app selection.
- Reopening the route resumes progress.
- Skip should not interrupt the main route.
- After the primary route is complete, offer REVISIT SKIPPED STOPS or FINISH ROUTE.
- Keep the interface large, high contrast, and low cognitive load.
- Avoid adding features unless they clearly reduce volunteer effort or organizer error.

## Navigation
Generated HTML should hand one destination at a time to the selected navigation app.
- Waze: deep link to coordinates.
- Google Maps: Maps URL to coordinates.
- Apple Maps: Maps URL to coordinates.
The navigation app handles live GPS, traffic, rerouting, and turn-by-turn directions.

## Development practices
- Python 3.11+.
- Keep functions small and testable.
- Add tests for parsing, route rotation, progress-state transitions, and output generation.
- Use deterministic fixtures in tests; tests must not depend on live geocoding/routing services.
- Preserve original source addresses alongside normalized/geocoded values.
- Write useful logs and human-readable validation output.
- Before broadening scope, complete the current milestone and run tests.

## Read first
Read `docs/PROJECT_SPEC.md` before implementation.
