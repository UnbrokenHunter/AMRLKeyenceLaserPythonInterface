"""
Main Textual orchestrator.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header

from src.display.panels.device_status_panel import DeviceStatusPanel
from src.bridge.bridge_controller import BridgeController
from src.bridge.bridge_events import BridgeEventType
from src.display.panels.continuous_keyence_panel import ContinuousKeyencePanel
from src.display.panels.control_bar import ControlBar
from src.display.panels.keyence_coms_panel import KeyenceComsPanel
from src.display.panels.spc_coms_panel import SpcComsPanel
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
            with Horizontal(id="content-row"):
                with Vertical(id="left-column"):
                    with Horizontal(id="coms-row"):
                        yield SpcComsPanel(id="spc-coms-panel")
                        yield KeyenceComsPanel(id="keyence-coms-panel")

                    yield ContinuousKeyencePanel(id="continuous-panel")

                yield StatusColumn(id="status-column")

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

    def on_control_bar_stream_toggle_changed(
        self,
        message: ControlBar.StreamToggleChanged,
    ) -> None:
        if message.enabled:
            self.controller.start_stream()
        else:
            self.controller.stop_stream()

        self._drain_controller_events()
        
    def on_control_bar_continuous_visibility_changed(
        self,
        message: ControlBar.ContinuousVisibilityChanged,
    ) -> None:
        self._set_continuous_panel_visible(message.visible)

    def on_control_bar_simulator_changed(self, message: ControlBar.SimulatorChanged) -> None:
        self.controller.set_simulator(message.enabled)
        self._drain_controller_events()

    def watch_show_continuous(self, show: bool) -> None:
        panel = self.query_one("#continuous-panel", ContinuousKeyencePanel)
        panel.set_class(show, "visible")

        control_bar = self.query_one("#controls", ControlBar)
        control_bar.set_continuous_visible(show)

        self._refresh_all_panels()

    def _set_continuous_panel_visible(self, visible: bool) -> None:
        self.show_continuous = visible
        self.controller.set_continuous_visible(visible)

        control_bar = self.query_one("#controls", ControlBar)
        control_bar.set_continuous_visible(visible)

        self._drain_controller_events()

    def action_toggle_continuous(self) -> None:
        self._set_continuous_panel_visible(not self.show_continuous)

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
                self.query_one("#spc-coms-panel", SpcComsPanel).log_received(
                    event.message
                )

            elif event.type == BridgeEventType.KEYENCE_SENT:
                self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_sent(
                    event.message
                )

            elif event.type == BridgeEventType.KEYENCE_RECEIVED:
                self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_received(
                    event.message
                )
                self.query_one("#continuous-panel", ContinuousKeyencePanel).log_data(
                    event.message
                )

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

        self.query_one("#spc-coms-panel", SpcComsPanel).set_port(
            state.spc.port
        )
        self.query_one("#keyence-coms-panel", KeyenceComsPanel).set_port(
            state.keyence.port
        )

        control_bar = self.query_one("#controls", ControlBar)
        control_bar.set_stream_enabled(state.streaming)
        control_bar.set_continuous_visible(state.continuous_visible)
        control_bar.set_simulator_enabled(state.use_simulator)

    def on_device_status_panel_port_changed(
        self,
        message: DeviceStatusPanel.PortChanged,
    ) -> None:
        status_column = self.query_one("#status-column", StatusColumn)

        self.controller.set_ports(
            keyence_port=status_column.get_keyence_port(),
            spc_port=status_column.get_spc_port(),
        )

        self._drain_controller_events()