from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label, Static

from src.bridge.bridge_state import DeviceViewState

SettingRows = list[tuple[str, str, str]]


class DeviceStatusPanel(Vertical):
    class PortChanged(Message):
        def __init__(self, port_id: str, port: str) -> None:
            super().__init__()
            self.port_id = port_id
            self.port = port

    class SettingChanged(Message):
        def __init__(self, port_id: str, setting: str, value: str) -> None:
            super().__init__()
            self.port_id = port_id
            self.setting = setting
            self.value = value

    def __init__(
        self,
        title: str,
        port_id: str,
        default_port: str,
        show_height: bool = True,
        settings: SettingRows | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.title = title
        self.port_id = port_id
        self.show_height = show_height
        self.status = DeviceViewState(port=default_port)
        self.force_port_refresh = False
        self.settings = settings or []
        self.setting_values = {
            setting_id: default_value
            for setting_id, _, default_value in self.settings
        }
        self.force_setting_refresh: set[str] = set()

    def compose(self) -> ComposeResult:
        self.add_class("panel")

        yield Label(self.title, id=f"{self.port_id}-title", classes="panel-title")
        yield Static("Connected: NO", id=f"{self.port_id}-connected", classes="status-line")

        if self.show_height:
            yield Static("Height: --", id=f"{self.port_id}-height", classes="status-line")

        yield Static("State: Idle", id=f"{self.port_id}-state", classes="status-line")
        with Horizontal(classes="port-row"):
            yield Label(
                "Port",
                id=f"{self.port_id}-port-label",
                classes="field-label port-label",
            )
            with Horizontal(classes="port-input-shell"):
                yield Input(
                    value=self.status.port,
                    id=f"{self.port_id}-port",
                    classes="port-input",
                    compact=True,
                )

        for setting_id, label, default_value in self.settings:
            with Horizontal(classes="port-row"):
                yield Label(
                    label,
                    id=f"{self.port_id}-{setting_id}-label",
                    classes="field-label port-label",
                )
                with Horizontal(classes="port-input-shell"):
                    yield Input(
                        value=default_value,
                        id=f"{self.port_id}-{setting_id}",
                        classes="port-input",
                        compact=True,
                    )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == f"{self.port_id}-port":
            self.force_port_refresh = True
            self._commit_port(event.input.value)
        else:
            setting = self._setting_from_input_id(event.input.id)
            if setting is not None:
                self.force_setting_refresh.add(setting)
                self._commit_setting(setting, event.input.value)

        event.input.blur()
        event.stop()

    def on_input_blurred(self, event: Input.Blurred) -> None:
        if event.input.id == f"{self.port_id}-port":
            self._commit_port(event.input.value)
        else:
            setting = self._setting_from_input_id(event.input.id)
            if setting is not None:
                self._commit_setting(setting, event.input.value)

        event.stop()

    def set_status(
        self,
        status: DeviceViewState,
        settings: dict[str, str] | None = None,
    ) -> None:
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

        if settings is not None:
            self.setting_values.update(settings)

        for setting_id, value in self.setting_values.items():
            setting_input = self.query_one(f"#{self.port_id}-{setting_id}", Input)

            if (
                setting_id in self.force_setting_refresh
                or not setting_input.has_focus
            ):
                setting_input.value = value
                self.force_setting_refresh.discard(setting_id)

    def get_port(self) -> str:
        return self.query_one(f"#{self.port_id}-port", Input).value.strip()

    def get_setting(self, setting: str) -> str:
        return self.query_one(f"#{self.port_id}-{setting}", Input).value.strip()

    def _commit_port(self, port: str) -> None:
        port = port.strip()

        if not port:
            self.query_one(f"#{self.port_id}-port", Input).value = self.status.port
            return

        self.status.port = port
        self.post_message(self.PortChanged(self.port_id, port))

    def _commit_setting(self, setting: str, value: str) -> None:
        value = value.strip()

        if not value:
            self.query_one(f"#{self.port_id}-{setting}", Input).value = (
                self.setting_values[setting]
            )
            return

        self.setting_values[setting] = value
        self.post_message(self.SettingChanged(self.port_id, setting, value))

    def _setting_from_input_id(self, input_id: str | None) -> str | None:
        if input_id is None:
            return None

        prefix = f"{self.port_id}-"

        if not input_id.startswith(prefix):
            return None

        setting = input_id.removeprefix(prefix)

        if setting == "port":
            return None

        if setting not in self.setting_values:
            return None

        return setting
