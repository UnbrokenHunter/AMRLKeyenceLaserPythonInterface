"""Hideable split panel for raw Keyence stream data and live height display."""

from __future__ import annotations

from collections import deque
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.widgets import Label, RichLog, Static


class HeightGraphPanel(Vertical):
    def __init__(self, *args, max_points: int = 120, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.values: deque[float] = deque(maxlen=max_points)

    def compose(self) -> ComposeResult:
        self.add_class("height-graph-panel")
        yield Label("Live Height", classes="panel-title")
        yield Static("Height: --", id="height-current-value", classes="height-current-value")
        yield Static("", id="height-graph")

    def add_height(self, height_mm: float | None) -> None:
        if height_mm is None:
            return

        self.values.append(height_mm)
        self._render_graph()

    def on_resize(self, _: Resize) -> None:
        self._render_graph()

    def _render_graph(self) -> None:
        graph = self.query_one("#height-graph", Static)
        value_label = self.query_one("#height-current-value", Static)

        if not self.values:
            value_label.update("Height: --")
            graph.update("")
            return

        latest = self.values[-1]
        value_label.update(f"Height: {latest:.5f} mm")

        values = list(self.values)

        min_value = min(values)
        max_value = max(values)

        if abs(max_value - min_value) < 1e-9:
            min_value -= 0.5
            max_value += 0.5

        rows = 8
        width = max(20, self.size.width - 9)

        visible_values = values[-width:]

        grid = [[" " for _ in range(width)] for _ in range(rows)]

        for x, value in enumerate(visible_values):
            normalized = (value - min_value) / (max_value - min_value)
            y = rows - 1 - round(normalized * (rows - 1))
            y = max(0, min(rows - 1, y))
            grid[y][x] = "─"

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
            f"[{self._time()}] {message}"
        )

    def add_height(self, height_mm: float | None) -> None:
        self.query_one("#height-graph-panel", HeightGraphPanel).add_height(height_mm)

    @staticmethod
    def _time() -> str:
        return datetime.now().strftime("%H:%M:%S")