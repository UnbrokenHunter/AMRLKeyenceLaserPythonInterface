"""
Main Textual orchestrator.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header

from src.bridge.bridge_controller import BridgeController
from src.bridge.bridge_events import BridgeEventType
from src.display.panels.continuous_keyence_panel import ContinuousKeyencePanel
from src.display.panels.control_bar import ControlBar
from src.display.panels.keyence_sent_panel import KeyenceSentPanel
from src.display.panels.spc_received_panel import SpcReceivedPanel
from src.display.panels.status_column import StatusColumn


class BridgeTuiApp(App):
    CSS_PATH = "terminal_app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "toggle_continuous", "Toggle continuous data"),
        ("s", "toggle_simulator", "Toggle simulator"),
        ("r", "read_once", "Read once"),
    ]

    show_continuous: reactive[bool] = reactive(False)

    def __init__(self, controller: BridgeController) -> None:
        super().__init__()
        self.controller = controller

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main"):
            with Horizontal(id="top-row"):
                yield SpcReceivedPanel(id="spc-received-panel")
                yield KeyenceSentPanel(id="keyence-sent-panel")
                yield StatusColumn(id="status-column")

            yield ContinuousKeyencePanel(id="continuous-panel")
            yield ControlBar(id="controls")

        yield Footer()

    def on_mount(self) -> None:
        self.title = "SpiiPlusSPC / Keyence Bridge Interface"
        self.sub_title = "AMRL Gen2 Laser System"

        self._refresh_all_panels()
        self._drain_controller_events()

        self.set_interval(0.1, self._tick)

    def on_control_bar_close_requested(self, _: ControlBar.CloseRequested) -> None:
        self.controller.close()
        self.exit()

    def on_control_bar_connect_requested(self, _: ControlBar.ConnectRequested) -> None:
        self._apply_ports_from_ui()
        self.controller.connect()
        self._drain_controller_events()

    def on_control_bar_read_once_requested(self, _: ControlBar.ReadOnceRequested) -> None:
        self.controller.read_once()
        self._drain_controller_events()

    def on_control_bar_start_stream_requested(self, _: ControlBar.StartStreamRequested) -> None:
        self.controller.start_stream()
        self._drain_controller_events()

    def on_control_bar_stop_stream_requested(self, _: ControlBar.StopStreamRequested) -> None:
        self.controller.stop_stream()
        self._drain_controller_events()

    def on_control_bar_continuous_visibility_changed(
        self,
        message: ControlBar.ContinuousVisibilityChanged,
    ) -> None:
        self.show_continuous = message.visible
        self.controller.set_continuous_visible(message.visible)
        self._drain_controller_events()

    def on_control_bar_simulator_changed(self, message: ControlBar.SimulatorChanged) -> None:
        self.controller.set_simulator(message.enabled)
        self._drain_controller_events()

    def watch_show_continuous(self, show: bool) -> None:
        panel = self.query_one("#continuous-panel", ContinuousKeyencePanel)
        panel.set_class(show, "visible")
        self._refresh_all_panels()

    def action_toggle_continuous(self) -> None:
        self.show_continuous = not self.show_continuous
        self.controller.set_continuous_visible(self.show_continuous)
        self._drain_controller_events()

    def action_toggle_simulator(self) -> None:
        self.controller.set_simulator(not self.controller.state.use_simulator)
        self._drain_controller_events()

    def action_read_once(self) -> None:
        self.controller.read_once()
        self._drain_controller_events()

    def _tick(self) -> None:
        self.controller.poll_stream_once()
        self._drain_controller_events()

    def _apply_ports_from_ui(self) -> None:
        status_column = self.query_one("#status-column", StatusColumn)
        self.controller.set_ports(
            keyence_port=status_column.get_keyence_port(),
            spc_port=status_column.get_spc_port(),
        )

    def _drain_controller_events(self) -> None:
        for event in self.controller.drain_events():
            if event.type == BridgeEventType.SPC_RECEIVED:
                self.query_one("#spc-received-panel", SpcReceivedPanel).log_command(event.message)

            elif event.type == BridgeEventType.KEYENCE_SENT:
                self.query_one("#keyence-sent-panel", KeyenceSentPanel).log_command(event.message)

            elif event.type == BridgeEventType.KEYENCE_RECEIVED:
                self.query_one("#continuous-panel", ContinuousKeyencePanel).log_data(event.message)

            elif event.type == BridgeEventType.ERROR:
                self.query_one("#continuous-panel", ContinuousKeyencePanel).log_data(
                    f"ERROR: {event.message}"
                )

            elif event.type == BridgeEventType.STATUS_CHANGED:
                pass

        self._refresh_all_panels()

    def _refresh_all_panels(self) -> None:
        state = self.controller.state
        self.query_one("#status-column", StatusColumn).set_state(state)
        self.query_one("#controls", ControlBar).set_state(state)