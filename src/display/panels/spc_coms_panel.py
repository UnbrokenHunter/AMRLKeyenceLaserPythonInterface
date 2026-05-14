"""Panel that displays SPC communications."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.widgets import Label, RichLog, Static


class SpcComsPanel(Vertical):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.show_tx = True
        self.show_rx = True

    def compose(self) -> ComposeResult:
        self.add_class("panel")

        with Horizontal(classes="panel-title-row"):
            yield Label("SPC Coms", classes="panel-title")
            yield Static("", id="spc-coms-port", classes="panel-title-port")
            yield Static("TX", id="spc-show-tx", classes="coms-filter-mini enabled")
            yield Static("RX", id="spc-show-rx", classes="coms-filter-mini enabled")

        yield RichLog(
            id="spc-received-log",
            wrap=True,
            auto_scroll=True,
            max_lines=500,
            classes="coms-log",
        )

    def on_click(self, event: Click) -> None:
        widget_id = event.widget.id if event.widget else None

        if widget_id == "spc-show-tx":
            self.show_tx = not self.show_tx
            self._set_filter_visual("#spc-show-tx", self.show_tx)
            event.stop()

        elif widget_id == "spc-show-rx":
            self.show_rx = not self.show_rx
            self._set_filter_visual("#spc-show-rx", self.show_rx)
            event.stop()

    def set_port(self, port: str) -> None:
        self.query_one("#spc-coms-port", Static).update(f"({port})")

    def log_received(self, message: str) -> None:
        if self.show_rx:
            self._log("RX", message)

    def log_sent(self, message: str) -> None:
        if self.show_tx:
            self._log("TX", message)

    def log_command(self, message: str) -> None:
        self.log_received(message)

    def _set_filter_visual(self, selector: str, enabled: bool) -> None:
        widget = self.query_one(selector, Static)
        widget.set_class(enabled, "enabled")
        widget.set_class(not enabled, "disabled")

    def _log(self, direction: str, message: str) -> None:
        self.query_one("#spc-received-log", RichLog).write(
            f"[{self._time()}] {direction:<2} | {message}"
        )

    @staticmethod
    def _time() -> str:
        return datetime.now().strftime("%H:%M:%S")