"""Hideable panel for continuous Keyence stream data."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, RichLog


class ContinuousKeyencePanel(Vertical):
    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield Label("Continuous Input Data Received from Keyence", classes="panel-title")
        yield RichLog(id="continuous-keyence-log", wrap=True, auto_scroll=True, max_lines=1000)

    def log_data(self, message: str) -> None:
        self.query_one("#continuous-keyence-log", RichLog).write(f"[{self._time()}] {message}")

    @staticmethod
    def _time() -> str:
        return datetime.now().strftime("%H:%M:%S")

