from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label, Static

from src.bridge.bridge_state import DeviceViewState


class DeviceStatusPanel(Vertical):
    class PortChanged(Message):
        def __init__(self, port_id: str, port: str) -> None:
            super().__init__()
            self.port_id = port_id
            self.port = port

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
        self.force_port_refresh = False

    def compose(self) -> ComposeResult:
        self.add_class("panel")

        yield Label(self.title, classes="panel-title")
        yield Static("Connected: NO", id=f"{self.port_id}-connected", classes="status-line")

        if self.show_height:
            yield Static("Height: --", id=f"{self.port_id}-height", classes="status-line")

        yield Static("State: Idle", id=f"{self.port_id}-state", classes="status-line")
        with Horizontal(classes="port-row"):
            yield Label("Port", classes="field-label port-label")
            yield Input(
                value=self.status.port,
                id=f"{self.port_id}-port",
                classes="port-input",
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.force_port_refresh = True
        self._commit_port(event.input.value)
        event.input.blur()
        event.stop()

    def on_input_blurred(self, event: Input.Blurred) -> None:
        self._commit_port(event.input.value)
        event.stop()

    def set_status(self, status: DeviceViewState) -> None:
        self.status = status

        connected_text = "Connected: YES" if status.connected else "Connected: NO"
        connected_line = self.query_one(f"#{self.port_id}-connected", Static)
        connected_line.update(connected_text)
        connected_line.set_class(status.connected, "connected-ok")
        connected_line.set_class(not status.connected, "connected-bad")

        self.query_one(f"#{self.port_id}-state", Static).update(f"State: {status.state}")

        if self.show_height:
            height_text = "Height: --" if status.height_mm is None else f"Height: {status.height_mm:.5f} mm"
            self.query_one(f"#{self.port_id}-height", Static).update(height_text)

        port_input = self.query_one(f"#{self.port_id}-port", Input)

        # Important:
        # Do NOT constantly overwrite the text box while the user is editing it.
        if self.force_port_refresh or not port_input.has_focus:
            port_input.value = status.port
            self.force_port_refresh = False

    def get_port(self) -> str:
        return self.query_one(f"#{self.port_id}-port", Input).value.strip()

    def _commit_port(self, port: str) -> None:
        port = port.strip()

        if not port:
            self.query_one(f"#{self.port_id}-port", Input).value = self.status.port
            return

        self.status.port = port
        self.post_message(self.PortChanged(self.port_id, port))
