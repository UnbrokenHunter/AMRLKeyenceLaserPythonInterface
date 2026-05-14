"""Reusable status panel for a device such as Keyence or SPC."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Label, Static

from src.bridge.bridge_state import DeviceViewState


class DeviceStatusPanel(Vertical):
    def __init__(
        self,
        title: str,
        port_id: str,
        default_port: str,
        show_height: bool = True,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.title = title
        self.port_id = port_id
        self.show_height = show_height
        self.status = DeviceViewState(port=default_port)

    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield Label(self.title, classes="panel-title")
        yield Static("Connected: NO", id=f"{self.port_id}-connected", classes="status-line")

        if self.show_height:
            yield Static("Height: --", id=f"{self.port_id}-height", classes="status-line")

        yield Static("State: Idle", id=f"{self.port_id}-state", classes="status-line")
        yield Label("Port", classes="field-label")
        yield Input(value=self.status.port, id=f"{self.port_id}-port")

    def set_status(self, status: DeviceViewState) -> None:
        self.status = status

        connected_text = "Connected: YES" if status.connected else "Connected: NO"
        self.query_one(f"#{self.port_id}-connected", Static).update(connected_text)
        self.query_one(f"#{self.port_id}-state", Static).update(f"State: {status.state}")

        port_input = self.query_one(f"#{self.port_id}-port", Input)
        if not port_input.has_focus:
            port_input.value = status.port

        if self.show_height:
            height_text = "Height: --" if status.height_mm is None else f"Height: {status.height_mm:.5f} mm"
            self.query_one(f"#{self.port_id}-height", Static).update(height_text)

    def get_port(self) -> str:
        return self.query_one(f"#{self.port_id}-port", Input).value.strip()
