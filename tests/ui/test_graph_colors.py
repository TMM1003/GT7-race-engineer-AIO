from __future__ import annotations

import unittest

from src.ui.graph_colors import (
    DEFAULT_GRAPH_COLOR_SETTINGS,
    graph_series_palette,
    normalized_graph_color_settings,
    overlay_series_palette,
)


class GraphColorSettingsTests(unittest.TestCase):
    def test_normalized_settings_fill_missing_values(self) -> None:
        settings = normalized_graph_color_settings(
            {
                "graph_speed": "#123456",
                "compare": "#abcdef",
            }
        )

        self.assertEqual(settings["graph_speed"], "#123456")
        self.assertEqual(settings["compare"], "#abcdef")
        self.assertEqual(
            settings["overlay_brake"],
            DEFAULT_GRAPH_COLOR_SETTINGS["overlay_brake"],
        )

    def test_normalized_settings_ignore_blank_values(self) -> None:
        settings = normalized_graph_color_settings(
            {
                "graph_rpm": "   ",
                "overlay_speed": "",
            }
        )

        self.assertEqual(
            settings["graph_rpm"],
            DEFAULT_GRAPH_COLOR_SETTINGS["graph_rpm"],
        )
        self.assertEqual(
            settings["overlay_speed"],
            DEFAULT_GRAPH_COLOR_SETTINGS["overlay_speed"],
        )

    def test_palette_helpers_split_graph_and_overlay_keys(self) -> None:
        settings = normalized_graph_color_settings(
            {
                "graph_speed": "#111111",
                "overlay_speed": "#222222",
            }
        )

        self.assertEqual(graph_series_palette(settings)["speed"], "#111111")
        self.assertEqual(overlay_series_palette(settings)["speed"], "#222222")


if __name__ == "__main__":
    unittest.main()
