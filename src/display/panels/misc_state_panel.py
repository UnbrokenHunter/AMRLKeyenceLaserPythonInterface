"""Panel that displays miscellaneous bridge state."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

from src.bridge.bridge_state import BridgeViewState


class MiscStatePanel(Vertical):
    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield Label("Bridge State", classes="panel-title")
        yield Static("", id="misc-state")

    def set_state(self, state: BridgeViewState) -> None:
        self.query_one("#misc-state", Static).update(
            f"Simulator: {'ON' if state.use_simulator else 'OFF'}\n"
            f"Streaming: {'ON' if state.streaming else 'OFF'}\n"
            f"Raw panel: {'shown' if state.continuous_visible else 'hidden'}\n"
            f"SPC RX: {state.spc_rx_count}\n"
            f"Keyence TX: {state.keyence_tx_count}\n"
            f"Keyence RX: {state.keyence_rx_count}\n"
            f"Error: {state.last_error or '--'}"
        )