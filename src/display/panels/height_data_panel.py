"""Hideable split panel for height source selection and graph display."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click, Resize
from textual.message import Message
from textual.widgets import Label, Select, Static

from src.bridge.csv_export import CsvHeightSample, export_height_samples
from src.input.input_client import InputReading
from src.input.keyence_protocol import parse_ms3_response, parse_stream_response


@dataclass(frozen=True)
class GraphSample:
    value_mm: float
    valid: bool
    timestamp: float | None = None
    layer_index: int = 0
    layer_sample_index: int | None = None


class HeightGraphPanel(Vertical):
    class InvalidVisibilityChanged(Message):
        def __init__(self, source: "HeightGraphPanel") -> None:
            super().__init__()
            self.source = source

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.samples: list[GraphSample] = []
        self.title = "Live Height"
        self.source_kind = "LIVE"
        self.include_invalid = True

    def compose(self) -> ComposeResult:
        self.add_class("height-graph-panel")
        with Horizontal(classes="height-title-row"):
            yield Label(self.title, id="height-graph-title", classes="panel-title")
            yield Static(
                "INV",
                id="height-include-invalid",
                classes="coms-filter-mini enabled height-invalid-toggle",
            )

        yield Static("Height: --", id="height-current-value", classes="height-current-value")
        yield Static(
            "Min: --  Max: --  Avg: --",
            id="height-graph-stats",
            classes="height-graph-stats",
        )
        yield Static("", id="height-graph")

    def on_click(self, event: Click) -> None:
        if event.widget and event.widget.id == "height-include-invalid":
            self.include_invalid = not self.include_invalid
            self._sync_invalid_toggle()
            self.post_message(self.InvalidVisibilityChanged(self))
            event.stop()

    def set_samples(
        self,
        title: str,
        samples: list[GraphSample],
        *,
        source_kind: str,
    ) -> None:
        self.title = title
        self.source_kind = source_kind
        self.samples = list(samples)
        self.query_one("#height-graph-title", Label).update(title)
        self._sync_invalid_toggle()
        self._render_graph()

    def set_include_invalid(self, include_invalid: bool) -> None:
        self.include_invalid = include_invalid
        self._sync_invalid_toggle()
        self._render_graph()

    def on_resize(self, _: Resize) -> None:
        self._render_graph()

    def _render_graph(self) -> None:
        graph = self.query_one("#height-graph", Static)
        value_label = self.query_one("#height-current-value", Static)
        stats_label = self.query_one("#height-graph-stats", Static)

        samples = self._display_samples()

        if not samples:
            value_label.update("Height: --")
            stats_label.update("Min: --  Max: --  Avg: --")
            graph.update("")
            return

        latest = samples[-1]

        if latest.valid:
            value_label.update(f"Height: {latest.value_mm:.5f} mm")
        else:
            value_label.update(f"Height: INVALID ({latest.value_mm:.5f} mm)")

        valid_values = [sample.value_mm for sample in samples if sample.valid]

        if valid_values:
            min_value = min(valid_values)
            max_value = max(valid_values)
            avg_value = sum(valid_values) / len(valid_values)
            stats_label.update(
                f"Min: {min_value:.5f}  Max: {max_value:.5f}  Avg: {avg_value:.5f}"
            )
        else:
            min_value = -1.0
            max_value = 1.0
            stats_label.update("Min: --  Max: --  Avg: --")

        if abs(max_value - min_value) < 1e-9:
            min_value -= 0.5
            max_value += 0.5

        rows = 8
        width = max(20, self.size.width - 9)
        visible_samples = self._samples_for_width(width)
        grid = [[" " for _ in range(width)] for _ in range(rows)]

        for x, sample in enumerate(visible_samples):
            if not sample.valid:
                for y in range(rows):
                    grid[y][x] = "x"
                continue

            normalized = (sample.value_mm - min_value) / (max_value - min_value)
            y = rows - 1 - round(normalized * (rows - 1))
            y = max(0, min(rows - 1, y))
            grid[y][x] = "-"

        lines: list[str] = []

        for row_index, row in enumerate(grid):
            if row_index == 0:
                label = f"{max_value:>7.3f} |"
            elif row_index == rows - 1:
                label = f"{min_value:>7.3f} |"
            else:
                label = "        |"

            lines.append(label + "".join(row))

        lines.append("        +" + "-" * width)
        lines.append("         " + self._axis_label(width))
        graph.update("\n".join(lines))

    def _samples_for_width(self, width: int) -> list[GraphSample]:
        samples = self._display_samples()

        if len(samples) <= width:
            return samples

        if self.source_kind == "LIVE":
            return samples[-width:]

        if width <= 1:
            return [samples[-1]]

        return [
            samples[round(index * (len(samples) - 1) / (width - 1))]
            for index in range(width)
        ]

    def _axis_label(self, width: int) -> str:
        if self.source_kind == "LIVE":
            timestamps = [
                sample.timestamp
                for sample in self._display_samples()
                if sample.timestamp is not None
            ]

            if not timestamps:
                left = "older"
            else:
                left = f"-{max(0.0, time.monotonic() - timestamps[0]):.1f}s"

            right = "now"
        else:
            left = "1"
            right = str(len(self._display_samples()))

        gap = max(1, width - len(left) - len(right))
        return left + (" " * gap) + right

    def _display_samples(self) -> list[GraphSample]:
        if self.include_invalid:
            return list(self.samples)

        return [sample for sample in self.samples if sample.valid]

    def _sync_invalid_toggle(self) -> None:
        toggle = self.query_one("#height-include-invalid", Static)
        toggle.set_class(self.include_invalid, "enabled")
        toggle.set_class(not self.include_invalid, "disabled")


@dataclass(frozen=True)
class HeightSource:
    key: str
    label: str
    samples: list[GraphSample]
    layers: dict[int, list[GraphSample]]
    current_layer_index: int = 0
    active: bool = False


class HeightSourceSelector(Vertical):
    class ExportRequested(Message):
        def __init__(self, source: "HeightSourceSelector") -> None:
            super().__init__()
            self.source = source

    def compose(self) -> ComposeResult:
        self.add_class("height-source-panel")
        yield Label("Height Source", classes="panel-title")
        yield Select(
            [("LIVE", "LIVE")],
            id="height-source-select",
            allow_blank=False,
            value="LIVE",
            classes="height-source-select",
        )
        yield Select(
            [("ALL LAYERS", "ALL")],
            id="height-layer-select",
            allow_blank=False,
            value="ALL",
            classes="height-source-select",
        )
        yield Static("", id="height-source-list")
        yield Static(
            "NEXT LAYER",
            id="height-next-layer",
            classes="coms-filter-mini enabled height-export-button",
        )
        yield Static(
            "EXPORT CSV",
            id="height-export-csv",
            classes="coms-filter-mini enabled height-export-button",
        )

    def on_click(self, event: Click) -> None:
        if event.widget and event.widget.id == "height-export-csv":
            self.post_message(self.ExportRequested(self))
            event.stop()

        if event.widget and event.widget.id == "height-next-layer":
            self.post_message(self.NextLayerRequested(self))
            event.stop()

    class NextLayerRequested(Message):
        def __init__(self, source: "HeightSourceSelector") -> None:
            super().__init__()
            self.source = source


class HeightDataPanel(Horizontal):
    class ExportCompleted(Message):
        def __init__(self, path: str | None, error: str | None = None) -> None:
            super().__init__()
            self.path = path
            self.error = error

    class NextLayerRequested(Message):
        def __init__(self, registry: str | None) -> None:
            super().__init__()
            self.registry = registry

    def __init__(self, *args, max_live_points: int = 120, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.live_samples: deque[GraphSample] = deque(maxlen=max_live_points)
        self.sources: list[HeightSource] = []
        self.selected_source_key = "LIVE"
        self.selected_layers: dict[str, str] = {}
        self.include_invalid = True

    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield HeightSourceSelector(id="height-source-panel", classes="height-data-half-panel")
        yield HeightGraphPanel(id="height-graph-panel", classes="height-data-half-panel")

    def log_data(self, message: str) -> None:
        return

    def add_keyence_response(self, message: str) -> None:
        try:
            reading = self._parse_keyence_response(message)
        except ValueError:
            return

        self.live_samples.append(
            GraphSample(
                value_mm=reading.value_mm,
                valid=reading.ok,
                timestamp=time.monotonic(),
                layer_index=0,
            )
        )

        if self.selected_source_key == "LIVE":
            self._render_selected_source()

    def add_height(self, height_mm: float | None) -> None:
        if height_mm is None:
            return

        self.live_samples.append(
            GraphSample(value_mm=height_mm, valid=True, timestamp=time.monotonic())
        )

        if self.selected_source_key == "LIVE":
            self._render_selected_source()

    def set_tracker_sources(
        self,
        trackers: dict[str, tuple[bool, int, dict[int, list[float]]]],
    ) -> None:
        self.sources = [
            HeightSource(
                key=f"TRACK:{registry}",
                label=(
                    f"{registry} "
                    f"({'ON' if active else 'OFF'}, {self._layer_count(layers)} samples, "
                    f"layer {current_layer})"
                ),
                samples=[
                    GraphSample(
                        value_mm=value,
                        valid=True,
                        layer_index=layer_index,
                        layer_sample_index=sample_index,
                    )
                    for layer_index, values in sorted(layers.items())
                    for sample_index, value in enumerate(values, start=1)
                ],
                layers={
                    layer_index: [
                        GraphSample(
                            value_mm=value,
                            valid=True,
                            layer_index=layer_index,
                            layer_sample_index=sample_index,
                        )
                        for sample_index, value in enumerate(values, start=1)
                    ]
                    for layer_index, values in sorted(layers.items())
                },
                current_layer_index=current_layer,
                active=active,
            )
            for registry, (active, current_layer, layers) in sorted(trackers.items())
        ]

        available_keys = {"LIVE"} | {source.key for source in self.sources}

        if self.selected_source_key not in available_keys:
            self.selected_source_key = "LIVE"

        self._render_source_select()
        self._render_layer_select()
        self._render_source_list()
        self._render_selected_source()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "height-source-select":
            return

        if isinstance(event.value, str):
            if event.select.id == "height-source-select":
                self.selected_source_key = event.value
                self._render_layer_select()
                self._render_source_list()
                self._render_selected_source()

            elif event.select.id == "height-layer-select":
                self.selected_layers[self.selected_source_key] = event.value
                self._render_source_list()
                self._render_selected_source()

        event.stop()

    def on_height_source_selector_export_requested(
        self,
        event: HeightSourceSelector.ExportRequested,
    ) -> None:
        event.stop()

        try:
            path = self.export_selected_source()
        except Exception as error:
            self.post_message(self.ExportCompleted(path=None, error=str(error)))
            return

        self.post_message(self.ExportCompleted(path=str(path)))

    def on_height_source_selector_next_layer_requested(
        self,
        event: HeightSourceSelector.NextLayerRequested,
    ) -> None:
        event.stop()
        self.post_message(self.NextLayerRequested(self._selected_registry()))

    def on_height_graph_panel_invalid_visibility_changed(
        self,
        event: HeightGraphPanel.InvalidVisibilityChanged,
    ) -> None:
        event.stop()
        self.include_invalid = event.source.include_invalid
        self._render_selected_source()

    def export_selected_source(self) -> Path:
        source_name = self._selected_export_name()
        now = time.monotonic()

        samples = [
            CsvHeightSample(
                value_mm=sample.value_mm,
                valid=sample.valid,
                seconds_ago=(
                    None
                    if sample.timestamp is None
                    else max(0.0, now - sample.timestamp)
                ),
                layer_index=sample.layer_index,
                layer_sample_index=sample.layer_sample_index,
            )
            for sample in self._selected_samples()
        ]

        return export_height_samples(source_name=source_name, samples=samples)

    def _render_source_list(self) -> None:
        layer_label = self._selected_layer_label()
        rows = [
            self._source_row(
                key="LIVE",
                label=f"LIVE ({len(self.live_samples)} samples)",
                active=True,
            )
        ]

        for source in self.sources:
            rows.append(
                self._source_row(
                    key=source.key,
                    label=(
                        f"{source.label}"
                        f"{' [view: ' + layer_label + ']' if source.key == self.selected_source_key else ''}"
                    ),
                    active=source.active,
                )
            )

        self.query_one("#height-source-list", Static).update("\n".join(rows))

    def _render_source_select(self) -> None:
        select = self.query_one("#height-source-select", Select)
        options = [("LIVE", "LIVE")] + [
            (source.label, source.key)
            for source in self.sources
        ]

        select.set_options(options)
        select.value = self.selected_source_key

    def _render_layer_select(self) -> None:
        select = self.query_one("#height-layer-select", Select)
        source = self._selected_tracker_source()

        if source is None:
            select.set_options([("ALL LAYERS", "ALL")])
            select.value = "ALL"
            return

        options = [("ALL LAYERS", "ALL")] + [
            (f"LAYER {layer_index}", str(layer_index))
            for layer_index in sorted(source.layers.keys())
        ]

        selected = self.selected_layers.get(source.key, "ALL")
        available_values = {value for _, value in options}

        if selected not in available_values:
            selected = "ALL"

        select.set_options(options)
        select.value = selected

    def _source_row(self, key: str, label: str, active: bool) -> str:
        selected = ">" if key == self.selected_source_key else " "
        state = "*" if active else " "
        return f"{selected} {state} {label}"

    def _render_selected_source(self) -> None:
        graph = self.query_one("#height-graph-panel", HeightGraphPanel)
        graph.set_include_invalid(self.include_invalid)

        if self.selected_source_key == "LIVE":
            graph.set_samples(
                "Live Height",
                list(self.live_samples),
                source_kind="LIVE",
            )
            return

        source = self._selected_tracker_source()

        if source is None:
            graph.set_samples(
                "Live Height",
                list(self.live_samples),
                source_kind="LIVE",
            )
            return

        graph.set_samples(
            f"Tracking {source.key.removeprefix('TRACK:')} ({self._selected_layer_label()})",
            self._selected_tracker_samples(source),
            source_kind="TRACK",
        )

    def _selected_samples(self) -> list[GraphSample]:
        if self.selected_source_key == "LIVE":
            samples = list(self.live_samples)
            return self._filter_invalid_samples(samples)

        source = self._selected_tracker_source()

        if source is None:
            return []

        return self._filter_invalid_samples(self._selected_tracker_samples(source))

    def _selected_export_name(self) -> str:
        if self.selected_source_key == "LIVE":
            return "live"

        return f"register-{self.selected_source_key.removeprefix('TRACK:')}"

    def _selected_registry(self) -> str | None:
        if not self.selected_source_key.startswith("TRACK:"):
            return None

        return self.selected_source_key.removeprefix("TRACK:")

    def _selected_tracker_source(self) -> HeightSource | None:
        return next(
            (
                source
                for source in self.sources
                if source.key == self.selected_source_key
            ),
            None,
        )

    def _selected_tracker_samples(self, source: HeightSource) -> list[GraphSample]:
        selected_layer = self.selected_layers.get(source.key, "ALL")

        if selected_layer == "ALL":
            return list(source.samples)

        try:
            layer_index = int(selected_layer)
        except ValueError:
            return list(source.samples)

        return list(source.layers.get(layer_index, []))

    def _selected_layer_label(self) -> str:
        source = self._selected_tracker_source()

        if source is None:
            return "ALL"

        selected_layer = self.selected_layers.get(source.key, "ALL")
        return "ALL" if selected_layer == "ALL" else f"LAYER {selected_layer}"

    def _filter_invalid_samples(self, samples: list[GraphSample]) -> list[GraphSample]:
        if self.include_invalid:
            return samples

        return [sample for sample in samples if sample.valid]

    @staticmethod
    def _layer_count(layers: dict[int, list[float]]) -> int:
        return sum(len(values) for values in layers.values())

    @staticmethod
    def _parse_keyence_response(message: str) -> InputReading:
        message = message.strip()

        if message.startswith("MS,"):
            return parse_ms3_response(message)

        return parse_stream_response(message)
