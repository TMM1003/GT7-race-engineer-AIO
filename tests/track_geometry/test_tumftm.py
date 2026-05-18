from __future__ import annotations

import unittest

from src.track_geometry.tumftm import canonical_track_key


class TumftmTrackMappingTests(unittest.TestCase):
    def test_retained_gt7_track_aliases_resolve_to_trackdb_stems(self) -> None:
        cases = {
            "Brands Hatch Grand Prix Circuit": "BrandsHatch",
            "Circuit de Barcelona-Catalunya": "Catalunya",
            "Circuit Gilles-Villeneuve": "Montreal",
            "Autodromo Nazionale Monza": "Monza",
            "Nürburgring GP": "Nuerburgring",
            "Autodromo de Interlagos": "SaoPaulo",
            "Circuit de Spa-Francorchamps": "Spa",
            "Red Bull Ring": "Spielberg",
            "Suzuka Circuit": "Suzuka",
            "Yas Marina Circuit": "YasMarina",
        }

        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(canonical_track_key(name), expected)

    def test_unsupported_variant_layouts_do_not_map_to_full_course_data(self) -> None:
        cases = [
            "Brands Hatch Indy Circuit",
            "Circuit de Barcelona-Catalunya National",
            "Autodromo Nazionale Monza No Chicane",
            "Nurburgring Nordschleife",
            "Red Bull Ring Short Track",
            "Suzuka Circuit East Course",
        ]

        for name in cases:
            with self.subTest(name=name):
                self.assertIsNone(canonical_track_key(name))


if __name__ == "__main__":
    unittest.main()
