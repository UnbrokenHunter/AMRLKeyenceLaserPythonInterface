"""Bottom control bar."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button


class ToggleButton(Button):
    def __init__(
        self,
        label: str,
        button_id: str,
        default_value: bool = False,
        on_label: str | None = None,
        off_label: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(label, id=button_id, **kwargs)

        self.on_label = on_label or label
        self.off_label = off_label or label
        self.enabled = default_value

    def on_mount(self) -> None:
        self.set_enabled(self.enabled)

    def toggle_enabled(self) -> bool:
        self.set_enabled(not self.enabled)
        return self.enabled

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.label = self.on_label if enabled else self.off_label
        self.set_class(enabled, "toggle-on")
        self.set_class(not enabled, "toggle-off")


class ControlBar(Horizontal):
    class CloseRequested(Message):
        pass

    class ConnectRequested(Message):
        pass

    class ReadOnceRequested(Message):
        pass

    class StreamToggleChanged(Message):
        def __init__(self, enabled: bool) -> None:
            super().__init__()
            self.enabled = enabled

    class ContinuousVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    class SimulatorChanged(Message):
        def __init__(self, enabled: bool) -> None:
            super().__init__()
            self.enabled = enabled

    class StatusVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    class SpcComsVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    class KeyenceComsVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    def compose(self) -> ComposeResult:
        self.add_class("control-bar")

        with Horizontal(classes="control-group"):
            yield Button("Close", id="close-button", variant="error", classes="control-button")
            yield Button("Connect", id="connect-button", variant="primary", classes="control-button")
            yield ToggleButton(
                "Simulator",
                button_id="simulator-toggle",
                default_value=True,
                on_label="Simulator: ON",
                off_label="Simulator: OFF",
                classes="control-button toggle-button",
            )

        with Horizontal(classes="control-group"):
            yield Button("Read", id="read-once-button", classes="control-button")
            yield ToggleButton(
                "Keyence Stream",
                button_id="stream-toggle",
                default_value=False,
                on_label="Keyence Stream: ON",
                off_label="Keyence Stream: OFF",
                classes="control-button toggle-button",
            )

        with Horizontal(classes="control-group"):
            yield ToggleButton(
                "Height Panel",
                button_id="continuous-toggle",
                default_value=False,
                on_label="Height: ON",
                off_label="Height: OFF",
                classes="control-button toggle-button view-toggle",
            )
            yield ToggleButton(
                "Status",
                button_id="status-toggle",
                default_value=True,
                on_label="Status: ON",
                off_label="Status: OFF",
                classes="control-button toggle-button view-toggle",
            )
            yield ToggleButton(
                "SPC Coms",
                button_id="spc-coms-toggle",
                default_value=True,
                on_label="SPC: ON",
                off_label="SPC: OFF",
                classes="control-button toggle-button view-toggle",
            )
            yield ToggleButton(
                "Keyence Coms",
                button_id="keyence-coms-toggle",
                default_value=True,
                on_label="Keyence: ON",
                off_label="Keyence: OFF",
                classes="control-button toggle-button view-toggle",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "close-button":
            self.post_message(self.CloseRequested())

        elif button_id == "connect-button":
            self.post_message(self.ConnectRequested())

        elif button_id == "read-once-button":
            self.post_message(self.ReadOnceRequested())

        elif button_id == "stream-toggle":
            enabled = self.query_one("#stream-toggle", ToggleButton).toggle_enabled()
            self.post_message(self.StreamToggleChanged(enabled))

        elif button_id == "continuous-toggle":
            visible = self.query_one("#continuous-toggle", ToggleButton).toggle_enabled()
            self.post_message(self.ContinuousVisibilityChanged(visible))

        elif button_id == "simulator-toggle":
            enabled = self.query_one("#simulator-toggle", ToggleButton).toggle_enabled()
            self.post_message(self.SimulatorChanged(enabled))

        elif button_id == "status-toggle":
            visible = self.query_one("#status-toggle", ToggleButton).toggle_enabled()
            self.post_message(self.StatusVisibilityChanged(visible))

        elif button_id == "spc-coms-toggle":
            visible = self.query_one("#spc-coms-toggle", ToggleButton).toggle_enabled()
            self.post_message(self.SpcComsVisibilityChanged(visible))

        elif button_id == "keyence-coms-toggle":
            visible = self.query_one("#keyence-coms-toggle", ToggleButton).toggle_enabled()
            self.post_message(self.KeyenceComsVisibilityChanged(visible))

    def set_stream_enabled(self, enabled: bool) -> None:
        self.query_one("#stream-toggle", ToggleButton).set_enabled(enabled)
        
    def set_continuous_visible(self, visible: bool) -> None:
        self.query_one("#continuous-toggle", ToggleButton).set_enabled(visible)

    def set_simulator_enabled(self, enabled: bool) -> None:
        self.query_one("#simulator-toggle", ToggleButton).set_enabled(enabled)

    def set_status_visible(self, visible: bool) -> None:
        self.query_one("#status-toggle", ToggleButton).set_enabled(visible)

    def set_spc_coms_visible(self, visible: bool) -> None:
        self.query_one("#spc-coms-toggle", ToggleButton).set_enabled(visible)

    def set_keyence_coms_visible(self, visible: bool) -> None:
        self.query_one("#keyence-coms-toggle", ToggleButton).set_enabled(visible)
    
