"""Panel that displays Keyence communications."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, RichLog, Static


class KeyenceSentPanel(Vertical):
    def compose(self) -> ComposeResult:
        self.add_class("panel")

        with Horizontal(classes="panel-title-row"):
            yield Label("Keyence Coms", classes="panel-title")
            yield Static("", id="keyence-coms-port", classes="panel-title-port")

        yield RichLog(
            id="keyence-sent-log",
            wrap=True,
            auto_scroll=True,
            max_lines=500,
            classes="coms-log",
        )

    def set_port(self, port: str) -> None:
        self.query_one("#keyence-coms-port", Static).update(f"({port})")

    def log_sent(self, message: str) -> None:
        self._log("TX", message)

    def log_received(self, message: str) -> None:
        self._log("RX", message)

    def log_command(self, message: str) -> None:
        self.log_sent(message)

    def _log(self, direction: str, message: str) -> None:
        self.query_one("#keyence-sent-log", RichLog).write(
            f"[{self._time()}] {direction:<2} | {message}"
        )

    @staticmethod
    def _time() -> str:
        return datetime.now().strftime("%H:%M:%S")