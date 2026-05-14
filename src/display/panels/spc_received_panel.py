"""Panel that displays SPC communications."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, RichLog, Static


class SpcReceivedPanel(Vertical):
    def compose(self) -> ComposeResult:
        self.add_class("panel")

        with Horizontal(classes="panel-title-row"):
            yield Label("SPC Coms", classes="panel-title")
            yield Static("", id="spc-coms-port", classes="panel-title-port")

        yield RichLog(
            id="spc-received-log",
            wrap=True,
            auto_scroll=True,
            max_lines=500,
            classes="coms-log",
        )

    def set_port(self, port: str) -> None:
        self.query_one("#spc-coms-port", Static).update(f"({port})")

    def log_received(self, message: str) -> None:
        self._log("RX", message)

    def log_sent(self, message: str) -> None:
        self._log("TX", message)

    def log_command(self, message: str) -> None:
        self.log_received(message)

    def _log(self, direction: str, message: str) -> None:
        self.query_one("#spc-received-log", RichLog).write(
            f"[{self._time()}] {direction:<2} | {message}"
        )

    @staticmethod
    def _time() -> str:
        return datetime.now().strftime("%H:%M:%S")