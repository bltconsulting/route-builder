import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from route_builder.prepare import prepare_route, route_name


class PrepareTests(unittest.TestCase):
    def test_name_is_portable(self):
        self.assertEqual(route_name(" North Route "), "North-Route")
        for name in ("../escape", "CON", "bad:name", "  "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                route_name(name)

    def test_review_then_generate_named_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "addresses.csv"
            source.write_text('id,address\n01,"1 Main St, Town, MI 48439"\n02,"2 Main St, Town, MI 48439"\n', encoding="utf-8")
            output = root / "routes"

            def validation_report(_, __, target):
                self._write_report(target, ["id", "source_address", "status"], "READY")

            def census_report(_, __, ___, target):
                self._write_report(target, ["id", "source_address", "census_result"], "MATCH")

            with patch("route_builder.prepare.NominatimGeocoder"), patch("route_builder.prepare.CensusGeocoder"), patch("route_builder.prepare.validate_csv", side_effect=validation_report), patch("route_builder.prepare.compare_csv", side_effect=census_report), patch("route_builder.prepare.write_census_review_map") as review_map:
                review_folder = prepare_route(source, "North Route", output)
            self.assertEqual(review_folder, output / "North-Route")
            self.assertFalse((review_folder / "North-Route.html").exists())
            self.assertTrue((review_folder / "review_input.json").exists())
            review_map.assert_called_once()

            with patch("route_builder.prepare.build_optimized_route") as build:
                target = prepare_route(source, "North Route", output, reviewed=True)
            self.assertEqual(target, review_folder / "North-Route.html")
            self.assertEqual(build.call_args.args[-1], "North-Route.html")

            source.write_text('id,address\n01,"Changed St, Town, MI 48439"\n02,"2 Main St, Town, MI 48439"\n', encoding="utf-8")
            with patch("route_builder.prepare.build_optimized_route") as build:
                with self.assertRaisesRegex(ValueError, "changed"):
                    prepare_route(source, "North Route", output, reviewed=True)
                build.assert_not_called()

    @staticmethod
    def _write_report(path, fields, result):
        with Path(path).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for stop_id, address in (("01", "1 Main St, Town, MI 48439"), ("02", "2 Main St, Town, MI 48439")):
                writer.writerow({"id": stop_id, "source_address": address, fields[-1]: result})


if __name__ == "__main__":
    unittest.main()
