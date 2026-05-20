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
            default_port="COM5",
            show_height=True,
            settings=[
                ("keyence_out_no", "OUT", "2"),
            ],
            id="keyence-status",
        )

        yield DeviceStatusPanel(
            title="SPC Status",
            port_id="spc",
            default_port="COM21",
            show_height=False,
            settings=[
                ("spc_baudrate", "Baud", "9600"),
                ("spc_line_ending", "Line", "CRLF"),
            ],
            id="spc-status",
        )

        yield MiscStatePanel(id="misc-state-panel")

    def set_state(self, state: BridgeViewState) -> None:
        self.query_one("#keyence-status", DeviceStatusPanel).set_status(
            state.keyence,
            settings={
                "keyence_out_no": str(state.keyence_out_no),
            },
        )
        self.query_one("#spc-status", DeviceStatusPanel).set_status(
            state.spc,
            settings={
                "spc_baudrate": str(state.spc_baudrate),
                "spc_line_ending": state.spc_line_ending,
            },
        )
        self.query_one("#misc-state-panel", MiscStatePanel).set_state(state)

    def get_keyence_port(self) -> str:
        return self.query_one("#keyence-status", DeviceStatusPanel).get_port()

    def get_spc_port(self) -> str:
        return self.query_one("#spc-status", DeviceStatusPanel).get_port()

    def get_keyence_out_no(self) -> str:
        return self.query_one("#keyence-status", DeviceStatusPanel).get_setting(
            "keyence_out_no"
        )

    def get_spc_baudrate(self) -> str:
        return self.query_one("#spc-status", DeviceStatusPanel).get_setting(
            "spc_baudrate"
        )

    def get_spc_line_ending(self) -> str:
        return self.query_one("#spc-status", DeviceStatusPanel).get_setting(
            "spc_line_ending"
        )
