"""Hideable split panel for height source selection and graph display."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.widgets import Label, Select, Static

from src.input.input_client import InputReading
from src.input.keyence_protocol import parse_ms3_response, parse_stream_response


@dataclass(frozen=True)
class GraphSample:
    value_mm: float
    valid: bool
    timestamp: float | None = None


class HeightGraphPanel(Vertical):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.samples: list[GraphSample] = []
        self.title = "Live Height"
        self.source_kind = "LIVE"

    def compose(self) -> ComposeResult:
        self.add_class("height-graph-panel")
        yield Label(self.title, id="height-graph-title", classes="panel-title")
        yield Static("Height: --", id="height-current-value", classes="height-current-value")
        yield Static(
            "Min: --  Max: --  Avg: --",
            id="height-graph-stats",
            classes="height-graph-stats",
        )
        yield Static("", id="height-graph")

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
        self._render_graph()

    def on_resize(self, _: Resize) -> None:
        self._render_graph()

    def _render_graph(self) -> None:
        graph = self.query_one("#height-graph", Static)
        value_label = self.query_one("#height-current-value", Static)
        stats_label = self.query_one("#height-graph-stats", Static)

        if not self.samples:
            value_label.update("Height: --")
            stats_label.update("Min: --  Max: --  Avg: --")
            graph.update("")
            return

        latest = self.samples[-1]

        if latest.valid:
            value_label.update(f"Height: {latest.value_mm:.5f} mm")
        else:
            value_label.update(f"Height: INVALID ({latest.value_mm:.5f} mm)")

        valid_values = [sample.value_mm for sample in self.samples if sample.valid]

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
        samples = list(self.samples)

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
                for sample in self.samples
                if sample.timestamp is not None
            ]

            if not timestamps:
                left = "older"
            else:
                left = f"-{max(0.0, time.monotonic() - timestamps[0]):.1f}s"

            right = "now"
        else:
            left = "1"
            right = str(len(self.samples))

        gap = max(1, width - len(left) - len(right))
        return left + (" " * gap) + right


@dataclass(frozen=True)
class HeightSource:
    key: str
    label: str
    samples: list[GraphSample]
    active: bool = False


class HeightSourceSelector(Vertical):
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
        yield Static("", id="height-source-list")


class ContinuousKeyencePanel(Horizontal):
    def __init__(self, *args, max_live_points: int = 120, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.live_samples: deque[GraphSample] = deque(maxlen=max_live_points)
        self.sources: list[HeightSource] = []
        self.selected_source_key = "LIVE"

    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield HeightSourceSelector(id="height-source-panel", classes="continuous-half-panel")
        yield HeightGraphPanel(id="height-graph-panel", classes="continuous-half-panel")

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

    def set_tracker_sources(self, trackers: dict[str, tuple[bool, list[float]]]) -> None:
        self.sources = [
            HeightSource(
                key=f"TRACK:{registry}",
                label=(
                    f"{registry} "
                    f"({'ON' if active else 'OFF'}, {len(values)} samples)"
                ),
                samples=[
                    GraphSample(value_mm=value, valid=True)
                    for value in values
                ],
                active=active,
            )
            for registry, (active, values) in sorted(trackers.items())
        ]

        available_keys = {"LIVE"} | {source.key for source in self.sources}

        if self.selected_source_key not in available_keys:
            self.selected_source_key = "LIVE"

        self._render_source_select()
        self._render_source_list()
        self._render_selected_source()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "height-source-select":
            return

        if isinstance(event.value, str):
            self.selected_source_key = event.value
            self._render_source_list()
            self._render_selected_source()

        event.stop()

    def _render_source_list(self) -> None:
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
                    label=source.label,
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

    def _source_row(self, key: str, label: str, active: bool) -> str:
        selected = ">" if key == self.selected_source_key else " "
        state = "*" if active else " "
        return f"{selected} {state} {label}"

    def _render_selected_source(self) -> None:
        graph = self.query_one("#height-graph-panel", HeightGraphPanel)

        if self.selected_source_key == "LIVE":
            graph.set_samples(
                "Live Height",
                list(self.live_samples),
                source_kind="LIVE",
            )
            return

        source = next(
            (
                source
                for source in self.sources
                if source.key == self.selected_source_key
            ),
            None,
        )

        if source is None:
            graph.set_samples(
                "Live Height",
                list(self.live_samples),
                source_kind="LIVE",
            )
            return

        graph.set_samples(
            f"Tracking {source.key.removeprefix('TRACK:')}",
            source.samples,
            source_kind="TRACK",
        )

    @staticmethod
    def _parse_keyence_response(message: str) -> InputReading:
        message = message.strip()

        if message.startswith("MS,"):
            return parse_ms3_response(message)

        return parse_stream_response(message)
