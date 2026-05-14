"""Panel that displays commands sent to the Keyence controller."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, RichLog


class KeyenceSentPanel(Vertical):
    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield Label("Commands Sent to Keyence", classes="panel-title")
        yield RichLog(id="keyence-sent-log", wrap=True, auto_scroll=True, max_lines=500)

    def log_command(self, message: str) -> None:
        self.query_one("#keyence-sent-log", RichLog).write(f"[{self._time()}] {message}")

    @staticmethod
    def _time() -> str:
        return datetime.now().strftime("%H:%M:%S")


