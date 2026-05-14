"""Bottom control bar."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label, Static, Switch

from src.bridge.bridge_state import BridgeViewState


class LabeledSwitch(Vertical):
    def __init__(
        self,
        label: str,
        switch_id: str,
        default_value: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.label = label
        self.switch_id = switch_id
        self.default_value = default_value

    def compose(self) -> ComposeResult:
        self.add_class("labeled-switch")
        yield Label(self.label, classes="switch-label")
        yield Switch(value=self.default_value, id=self.switch_id)


class ControlBar(Horizontal):
    class CloseRequested(Message):
        pass

    class ConnectRequested(Message):
        pass

    class ReadOnceRequested(Message):
        pass

    class StartStreamRequested(Message):
        pass

    class StopStreamRequested(Message):
        pass

    class ContinuousVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    class SimulatorChanged(Message):
        def __init__(self, enabled: bool) -> None:
            super().__init__()
            self.enabled = enabled

    def compose(self) -> ComposeResult:
        self.add_class("control-bar")

        yield Button("Close App", id="close-button", variant="error")
        yield Button("Connect Ports", id="connect-button", variant="primary")
        yield Button("Read Height Once", id="read-once-button")
        yield Button("Start Keyence Stream", id="start-stream-button", variant="success")
        yield Button("Stop Keyence Stream", id="stop-stream-button")

        yield LabeledSwitch(
            label="Show Raw Keyence Stream",
            switch_id="continuous-toggle",
            default_value=False,
        )

        yield LabeledSwitch(
            label="Use Simulated Keyence",
            switch_id="simulator-toggle",
            default_value=True,
        )

        yield Static(id="misc-state")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "close-button":
            self.post_message(self.CloseRequested())

        elif button_id == "connect-button":
            self.post_message(self.ConnectRequested())

        elif button_id == "read-once-button":
            self.post_message(self.ReadOnceRequested())

        elif button_id == "start-stream-button":
            self.post_message(self.StartStreamRequested())

        elif button_id == "stop-stream-button":
            self.post_message(self.StopStreamRequested())

    def on_switch_changed(self, event: Switch.Changed) -> None:
        switch_id = event.switch.id

        if switch_id == "continuous-toggle":
            self.post_message(self.ContinuousVisibilityChanged(event.value))

        elif switch_id == "simulator-toggle":
            self.post_message(self.SimulatorChanged(event.value))

    def set_state(self, state: BridgeViewState) -> None:
        self.query_one("#misc-state", Static).update(
            f"Simulator: {'ON' if state.use_simulator else 'OFF'} | "
            f"Streaming: {'ON' if state.streaming else 'OFF'} | "
            f"Raw panel: {'shown' if state.continuous_visible else 'hidden'} | "
            f"SPC RX: {state.spc_rx_count} | "
            f"Keyence TX: {state.keyence_tx_count} | "
            f"Keyence RX: {state.keyence_rx_count} | "
            f"Error: {state.last_error or '--'}"
        )