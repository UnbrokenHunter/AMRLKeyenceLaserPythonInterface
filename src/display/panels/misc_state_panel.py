"""Panel that displays miscellaneous bridge state."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

from src.bridge.bridge_state import BridgeViewState


class MiscStatePanel(Vertical):
    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield Label("Bridge State", classes="panel-title")
        yield Static("", id="misc-state")
        yield Static("Error: --", id="misc-error")

    def set_state(self, state: BridgeViewState) -> None:
        self.query_one("#misc-state", Static).update(
            Text(
                f"Simulator: {'ON' if state.use_simulator else 'OFF'}\n"
                f"Streaming: {'ON' if state.streaming else 'OFF'}\n"
                f"Height panel: {'shown' if state.continuous_visible else 'hidden'}\n"
                f"Keyence OUT: {state.keyence_out_no}\n"
                f"SPC baud: {state.spc_baudrate}\n"
                f"SPC line: {state.spc_line_ending}\n"
                f"SPC RX: {state.spc_rx_count}\n"
                f"SPC TX: {state.spc_tx_count}\n"
                f"Keyence TX: {state.keyence_tx_count}\n"
                f"Keyence RX: {state.keyence_rx_count}"
            )
        )
        error_line = self.query_one("#misc-error", Static)
        has_error = bool(state.last_error)
        error_line.update(f"Error: {self._format_error(state.last_error)}")
        error_line.set_class(has_error, "error-active")

    @staticmethod
    def _format_error(error: str | None) -> str:
        if not error:
            return "--"

        error = error.replace("\n", " ")

        max_len = 120
        if len(error) > max_len:
            return error[:max_len] + "..."

        return error
