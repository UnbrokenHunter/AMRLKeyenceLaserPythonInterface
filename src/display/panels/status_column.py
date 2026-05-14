from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical

from src.bridge.bridge_state import BridgeViewState
from src.display.panels.device_status_panel import DeviceStatusPanel
from src.display.panels.misc_state_panel import MiscStatePanel


class StatusColumn(Vertical):
    def compose(self) -> ComposeResult:
        yield DeviceStatusPanel(
            title="Keyence Status",
            port_id="keyence",
            default_port="COM3",
            show_height=True,
            id="keyence-status",
        )

        yield DeviceStatusPanel(
            title="SPC Status",
            port_id="spc",
            default_port="COM9",
            show_height=False,
            id="spc-status",
        )

        yield MiscStatePanel(id="misc-state-panel")

    def set_state(self, state: BridgeViewState) -> None:
        self.query_one("#keyence-status", DeviceStatusPanel).set_status(state.keyence)
        self.query_one("#spc-status", DeviceStatusPanel).set_status(state.spc)
        self.query_one("#misc-state-panel", MiscStatePanel).set_state(state)

    def get_keyence_port(self) -> str:
        return self.query_one("#keyence-status", DeviceStatusPanel).get_port()

    def get_spc_port(self) -> str:
        return self.query_one("#spc-status", DeviceStatusPanel).get_port()