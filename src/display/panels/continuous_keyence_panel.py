"""Hideable split panel for raw Keyence stream data and live height display."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.widgets import Label, RichLog, Static

from src.input.input_client import InputReading
from src.input.keyence_protocol import parse_ms3_response, parse_stream_response


@dataclass(frozen=True)
class GraphSample:
    value_mm: float
    valid: bool


class HeightGraphPanel(Vertical):
    def __init__(self, *args, max_points: int = 120, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.samples: deque[GraphSample] = deque(maxlen=max_points)

    def compose(self) -> ComposeResult:
        self.add_class("height-graph-panel")
        yield Label("Live Height", classes="panel-title")
        yield Static("Height: --", id="height-current-value", classes="height-current-value")
        yield Static("", id="height-graph")

    def add_reading(self, reading: InputReading) -> None:
        self.samples.append(
            GraphSample(
                value_mm=reading.value_mm,
                valid=reading.ok,
            )
        )
        self._render_graph()

    def add_height(self, height_mm: float | None) -> None:
        """
        Backwards-compatible method.

        Treats manually supplied height values as valid.
        """
        if height_mm is None:
            return

        self.samples.append(GraphSample(value_mm=height_mm, valid=True))
        self._render_graph()

    def on_resize(self, _: Resize) -> None:
        self._render_graph()

    def _render_graph(self) -> None:
        graph = self.query_one("#height-graph", Static)
        value_label = self.query_one("#height-current-value", Static)

        if not self.samples:
            value_label.update("Height: --")
            graph.update("")
            return

        latest = self.samples[-1]

        if latest.valid:
            value_label.update(f"Height: {latest.value_mm:.5f} mm")
        else:
            value_label.update(f"Height: INVALID ({latest.value_mm:.5f} mm)")

        # Use only valid values to scale the graph. Invalid sentinel values like
        # -99.9999 should not crush the useful graph range.
        valid_values = [sample.value_mm for sample in self.samples if sample.valid]

        if valid_values:
            min_value = min(valid_values)
            max_value = max(valid_values)
        else:
            min_value = -1.0
            max_value = 1.0

        if abs(max_value - min_value) < 1e-9:
            min_value -= 0.5
            max_value += 0.5

        rows = 8
        width = max(20, self.size.width - 9)

        visible_samples = list(self.samples)[-width:]

        grid = [[" " for _ in range(width)] for _ in range(rows)]

        for x, sample in enumerate(visible_samples):
            if sample.valid:
                value_for_plot = sample.value_mm
                symbol = "─"
            else:
                # Invalid values should appear as x's, but should not rescale the graph.
                # Put them on the closest edge depending on whether they are below/above range. (DOSNT WORK) TODO fix this
                value_for_plot = max(min(sample.value_mm, max_value), min_value)
                symbol = "x"

            normalized = (value_for_plot - min_value) / (max_value - min_value)
            y = rows - 1 - round(normalized * (rows - 1))
            y = max(0, min(rows - 1, y))

            grid[y][x] = symbol

        lines: list[str] = []

        for row_index, row in enumerate(grid):
            if row_index == 0:
                label = f"{max_value:>7.3f} │"
            elif row_index == rows - 1:
                label = f"{min_value:>7.3f} │"
            else:
                label = "        │"

            lines.append(label + "".join(row))

        lines.append("        └" + "─" * width)

        graph.update("\n".join(lines))


class ContinuousKeyencePanel(Horizontal):
    def compose(self) -> ComposeResult:
        self.add_class("panel")

        with Vertical(id="raw-keyence-stream-panel", classes="continuous-half-panel"):
            yield Label("Continuous Input Data Received from Keyence", classes="panel-title")
            yield RichLog(
                id="continuous-keyence-log",
                wrap=True,
                auto_scroll=True,
                max_lines=1000,
            )

        yield HeightGraphPanel(id="height-graph-panel", classes="continuous-half-panel")

    def log_data(self, message: str) -> None:
        self.query_one("#continuous-keyence-log", RichLog).write(
            Text(f"[{self._time()}] {message}")
        )

    def add_keyence_response(self, message: str) -> None:
        """
        Parse a Keyence response/stream line and add it to the graph.

        Supports:
            MS,-01.2345,0,GO
            -01.2345,0,GO
            NS,-01.2345,0,GO
        """
        try:
            reading = self._parse_keyence_response(message)
        except ValueError:
            return

        self.query_one("#height-graph-panel", HeightGraphPanel).add_reading(reading)

    def add_height(self, height_mm: float | None) -> None:
        self.query_one("#height-graph-panel", HeightGraphPanel).add_height(height_mm)

    @staticmethod
    def _parse_keyence_response(message: str) -> InputReading:
        message = message.strip()

        if message.startswith("MS,"):
            return parse_ms3_response(message)

        return parse_stream_response(message)

    @staticmethod
    def _time() -> str:
        return datetime.now().strftime("%H:%M:%S")