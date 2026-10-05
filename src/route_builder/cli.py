"""Local route builder commands."""

import argparse
import logging
from pathlib import Path

from .generate import build_stops, build_stops_from_census, generate_html
from .geocode import NominatimGeocoder, validate_csv
from .review_map import write_review_map
from .census import CensusGeocoder, compare_csv
from .routing import build_optimized_route
from .multi_route import build_multi_route_csv
from .printable_maps import write_printable_maps
from .volunteer_pages import write_volunteer_pages
from .prepare import prepare_route, NOMINATIM_ENDPOINT, OSRM_ENDPOINT, USER_AGENT


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local volunteer route demo")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Generate route.html using fixture coordinates")
    build.add_argument("input_csv")
    coordinates = build.add_mutually_exclusive_group(required=True)
    coordinates.add_argument("--fixture", help="JSON mapping stop IDs to demo coordinates")
    coordinates.add_argument("--census-comparison", help="Census comparison CSV for a test-only route")
    build.add_argument("--output", default="build")
    validate = sub.add_parser("validate", help="Geocode addresses into an organizer review CSV")
    validate.add_argument("input_csv")
    validate.add_argument("--endpoint", required=True, help="HTTPS Nominatim-compatible search endpoint")
    validate.add_argument("--user-agent", required=True, help="Identifying application User-Agent")
    validate.add_argument("--output", default="build")
    review = sub.add_parser("review-map", help="Create an offline coordinate overview from validation.csv")
    review.add_argument("validation_csv")
    review.add_argument("--output", default="build/geocode_review.html")
    census = sub.add_parser("compare-census", help="Compare Census address matches with the Nominatim review report")
    census.add_argument("input_csv")
    census.add_argument("--validation", default="build/validation.csv")
    census.add_argument("--output", default="build")
    optimize = sub.add_parser("optimize", help="Build a closed road-driving loop from reviewed test coordinates")
    optimize.add_argument("input_csv")
    optimize.add_argument("--census-comparison", required=True)
    optimize.add_argument("--matrix-endpoint", required=True, help="HTTPS OSRM-compatible routing endpoint")
    optimize.add_argument("--output", default="build/optimized")
    multiple = sub.add_parser("plan-routes", help="Group reviewed stops and order each closed route")
    multiple.add_argument("input_csv")
    multiple.add_argument("--census-comparison", required=True)
    multiple.add_argument("--routes", required=True, type=int, help="Number of balanced routes")
    multiple.add_argument("--matrix-endpoint", default=OSRM_ENDPOINT)
    multiple.add_argument("--output", default="build/multi_routes")
    maps = sub.add_parser("print-maps", help="Make offline printable road maps for planned routes")
    maps.add_argument("routes_csv", help="routes.csv from plan-routes")
    maps.add_argument("--roads-zip", required=True, help="County TIGER/Line roads ZIP")
    maps.add_argument("--output", default="build/printable_route_maps.html")
    pages = sub.add_parser("volunteer-pages", help="Create one navigation widget per planned route")
    pages.add_argument("routes_csv", help="routes.csv from plan-routes")
    pages.add_argument("--output", default="build/volunteer_pages")
    prepare = sub.add_parser("prepare", help="Review addresses, then create one named volunteer route")
    prepare.add_argument("input_csv")
    prepare.add_argument("--name", required=True, help="Route name; becomes a folder and HTML filename")
    prepare.add_argument("--output", default="build/routes")
    prepare.add_argument("--reviewed", action="store_true", help="I inspected the reports and destination pins; build the route")
    prepare.add_argument("--geocoder-endpoint", default=NOMINATIM_ENDPOINT)
    prepare.add_argument("--matrix-endpoint", default=OSRM_ENDPOINT)
    prepare.add_argument("--user-agent", default=USER_AGENT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if args.command == "build":
        try:
            if args.census_comparison:
                stops = build_stops_from_census(args.input_csv, args.census_comparison)
                notice = "TEST ONLY: Census coordinates are estimated along street ranges. Verify each destination before driving; this route has not been optimized or approved."
            else:
                stops = build_stops(args.input_csv, args.fixture)
                notice = "DEMO ONLY: these coordinates are placeholders. Do not use this route for deliveries."
            template_dir = Path(__file__).resolve().parents[2] / "templates"
            html = generate_html(stops, template_dir, notice)
        except (OSError, ValueError) as exc:
            parser.exit(2, f"Input error: {exc}\n")
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        target = output / "route.html"
        target.write_text(html, encoding="utf-8")
        logging.info("Generated %s with %d stops in supplied loop order (%s)", target, len(stops), "Census test coordinates" if args.census_comparison else "demo coordinates")
    elif args.command == "validate":
        output = Path(args.output)
        try:
            geocoder = NominatimGeocoder(args.endpoint, args.user_agent, output / "geocode_cache.json")
            validate_csv(args.input_csv, geocoder, output / "validation.csv")
        except (OSError, ValueError) as exc:
            parser.exit(2, f"Geocoding error: {exc}\n")
    elif args.command == "review-map":
        try:
            target = write_review_map(args.validation_csv, args.output)
        except (OSError, ValueError) as exc:
            parser.exit(2, f"Review map error: {exc}\n")
        logging.info("Wrote %s", target)
    elif args.command == "compare-census":
        output = Path(args.output)
        try:
            geocoder = CensusGeocoder(output / "census_cache.json")
            compare_csv(args.input_csv, args.validation, geocoder, output / "census_comparison.csv")
        except (OSError, ValueError, KeyError) as exc:
            parser.exit(2, f"Census comparison error: {exc}\n")
    elif args.command == "optimize":
        try:
            build_optimized_route(args.input_csv, args.census_comparison, args.output, args.matrix_endpoint)
        except (OSError, ValueError, ImportError) as exc:
            parser.exit(2, f"Routing error: {exc}\n")
    elif args.command == "plan-routes":
        try:
            target = build_multi_route_csv(args.input_csv, args.census_comparison,
                                           args.routes, args.output, args.matrix_endpoint)
        except (OSError, ValueError, ImportError, KeyError) as exc:
            parser.exit(2, f"Multi-route error: {exc}\n")
        logging.info("Wrote %s", target)
    elif args.command == "print-maps":
        try:
            target = write_printable_maps(args.routes_csv, args.roads_zip, args.output)
        except (OSError, ValueError, KeyError) as exc:
            parser.exit(2, f"Map error: {exc}\n")
        logging.info("Wrote %s", target)
    elif args.command == "volunteer-pages":
        try:
            targets = write_volunteer_pages(args.routes_csv, args.output)
        except (OSError, ValueError, KeyError) as exc:
            parser.exit(2, f"Volunteer page error: {exc}\n")
        logging.info("Wrote %d volunteer review pages in %s", len(targets), args.output)
    elif args.command == "prepare":
        try:
            target = prepare_route(args.input_csv, args.name, args.output, reviewed=args.reviewed,
                                   geocoder_endpoint=args.geocoder_endpoint,
                                   matrix_endpoint=args.matrix_endpoint, user_agent=args.user_agent)
        except (OSError, ValueError, KeyError, ImportError) as exc:
            parser.exit(2, f"Prepare error: {exc}\n")
        if args.reviewed:
            logging.info("Volunteer file: %s", target)
        else:
            logging.warning("Review %s/validation.csv, census_comparison.csv, and geocode_review.html; inspect every destination pin. Then rerun with --reviewed to build the route.", target)

if __name__ == "__main__":
    main()
