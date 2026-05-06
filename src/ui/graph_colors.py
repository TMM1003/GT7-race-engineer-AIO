from __future__ import annotations

from collections.abc import Mapping


GRAPH_METRICS = ("speed", "rpm", "throttle", "brake")

DEFAULT_GRAPH_COLOR_SETTINGS = {
    "graph_speed": "#3498db",
    "graph_rpm": "#9b59b6",
    "graph_throttle": "#2ecc71",
    "graph_brake": "#e74c3c",
    "overlay_speed": "#3498db",
    "overlay_rpm": "#9b59b6",
    "overlay_throttle": "#2ecc71",
    "overlay_brake": "#e74c3c",
    "compare": "#ff9f1c",
}


def normalized_graph_color_settings(
    values: Mapping[str, object] | None,
) -> dict[str, str]:
    settings = dict(DEFAULT_GRAPH_COLOR_SETTINGS)
    if not values:
        return settings

    for key in settings:
        value = values.get(key)
        if isinstance(value, str):
            color = value.strip()
            if color:
                settings[key] = color
    return settings


def graph_series_palette(settings: Mapping[str, object] | None) -> dict[str, str]:
    resolved = normalized_graph_color_settings(settings)
    return {
        metric: resolved[f"graph_{metric}"]
        for metric in GRAPH_METRICS
    }


def overlay_series_palette(
    settings: Mapping[str, object] | None,
) -> dict[str, str]:
    resolved = normalized_graph_color_settings(settings)
    return {
        metric: resolved[f"overlay_{metric}"]
        for metric in GRAPH_METRICS
    }
