"""
Main Textual orchestrator.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import MouseMove
from textual.reactive import reactive
from textual.widgets import Header

from src.display.panels.common_coms_panel import CommonComsPanel
from src.display.panels.device_status_panel import DeviceStatusPanel
from src.bridge.bridge_controller import BridgeController
from src.bridge.bridge_events import BridgeEventType
from src.display.hover_help import DEFAULT_HELP_TEXT, HelpBar, get_hover_help
from src.display.hover_help_registry import install_hover_help
from src.display.panels.continuous_keyence_panel import ContinuousKeyencePanel
from src.display.panels.control_bar import ControlBar
from src.display.panels.keyence_coms_panel import KeyenceComsPanel
from src.display.panels.spc_command_docs_panel import SpcCommandDocsPanel
from src.display.panels.spc_coms_panel import SpcComsPanel
from src.display.panels.status_column import StatusColumn


class BridgeTuiApp(App):
    CSS_PATH = "terminal_app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "toggle_continuous", "Toggle height panel"),
        ("s", "toggle_simulator", "Toggle simulator"),
        ("r", "read_once", "Read once"),
    ]

    show_continuous: reactive[bool] = reactive(False)
    show_status: reactive[bool] = reactive(True)
    show_spc_coms: reactive[bool] = reactive(True)
    show_keyence_coms: reactive[bool] = reactive(True)
    show_spc_docs: reactive[bool] = reactive(False)

    def __init__(self, controller: BridgeController) -> None:
        super().__init__()
        self.controller = controller
        self._current_help_text = DEFAULT_HELP_TEXT

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main"):
            with Horizontal(id="content-row"):
                with Vertical(id="left-column"):
                    with Horizontal(id="coms-row"):
                        yield SpcCommandDocsPanel(id="spc-docs-panel")
                        yield SpcComsPanel(id="spc-coms-panel")
                        yield KeyenceComsPanel(id="keyence-coms-panel")

                    yield ContinuousKeyencePanel(id="continuous-panel")

                yield StatusColumn(id="status-column")

            yield ControlBar(id="controls")

        yield HelpBar(DEFAULT_HELP_TEXT, id="help-footer")
                
    def on_mount(self) -> None:
        self.title = "SpiiPlusSPC / Keyence Bridge Interface"
        self.sub_title = "AMRL Gen2 Laser System"

        self._refresh_all_panels()
        self._drain_controller_events()
        install_hover_help(self)

        self.set_interval(0.1, self._tick)

    def on_mouse_move(self, event: MouseMove) -> None:
        help_text = get_hover_help(event.widget) or DEFAULT_HELP_TEXT

        if help_text == self._current_help_text:
            return

        self._current_help_text = help_text
        self.query_one("#help-footer", HelpBar).compose_help(help_text)

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

    def on_control_bar_status_visibility_changed(
        self,
        message: ControlBar.StatusVisibilityChanged,
    ) -> None:
        self.show_status = message.visible

    def on_control_bar_spc_coms_visibility_changed(
        self,
        message: ControlBar.SpcComsVisibilityChanged,
    ) -> None:
        self.show_spc_coms = message.visible

    def on_control_bar_keyence_coms_visibility_changed(
        self,
        message: ControlBar.KeyenceComsVisibilityChanged,
    ) -> None:
        self.show_keyence_coms = message.visible

    def on_control_bar_spc_docs_visibility_changed(
        self,
        message: ControlBar.SpcDocsVisibilityChanged,
    ) -> None:
        self.show_spc_docs = message.visible

    def on_common_coms_panel_command_submitted(
        self,
        message: CommonComsPanel.CommandSubmitted,
    ) -> None:
        if isinstance(message.source, KeyenceComsPanel):
            self.controller.send_keyence_command(message.command, emit_sent=False)
            self._drain_controller_events()
            return

        if isinstance(message.source, SpcComsPanel):
            self.controller.send_spc_command(message.command, emit_sent=False)
            self._drain_controller_events()
            return

    def watch_show_continuous(self, show: bool) -> None:
        self.query_one("#continuous-panel", ContinuousKeyencePanel).set_class(
            show,
            "visible",
        )

        control_bar = self.query_one("#controls", ControlBar)
        control_bar.set_continuous_visible(show)

        self._refresh_all_panels()

    def watch_show_status(self, show: bool) -> None:
        self.query_one("#status-column", StatusColumn).set_class(not show, "hidden")
        self.query_one("#controls", ControlBar).set_status_visible(show)

    def watch_show_spc_coms(self, show: bool) -> None:
        self.query_one("#spc-coms-panel", SpcComsPanel).set_class(not show, "hidden")
        self.query_one("#controls", ControlBar).set_spc_coms_visible(show)

    def watch_show_keyence_coms(self, show: bool) -> None:
        self.query_one("#keyence-coms-panel", KeyenceComsPanel).set_class(not show, "hidden")
        self.query_one("#controls", ControlBar).set_keyence_coms_visible(show)

    def watch_show_spc_docs(self, show: bool) -> None:
        self.query_one("#spc-docs-panel", SpcCommandDocsPanel).set_class(
            not show,
            "hidden",
        )
        self.query_one("#controls", ControlBar).set_spc_docs_visible(show)

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
        self.controller.poll_spc_once()
        self._drain_controller_events()

    def _apply_ports_from_ui(self) -> None:
        status_column = self.query_one("#status-column", StatusColumn)
        self.controller.set_connection_config(
            keyence_port=status_column.get_keyence_port(),
            spc_port=status_column.get_spc_port(),
            keyence_out_no=status_column.get_keyence_out_no(),
            spc_baudrate=status_column.get_spc_baudrate(),
            spc_line_ending=status_column.get_spc_line_ending(),
        )

    def _drain_controller_events(self) -> None:
        for event in self.controller.drain_events():
            if event.type == BridgeEventType.SPC_RECEIVED:
                self.query_one("#spc-coms-panel", SpcComsPanel).receive_data(
                    event.message
                )

            elif event.type == BridgeEventType.SPC_SENT:
                self.query_one("#spc-coms-panel", SpcComsPanel).log_sent(
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

                continuous_panel = self.query_one("#continuous-panel", ContinuousKeyencePanel)
                continuous_panel.log_data(event.message)
                continuous_panel.add_keyence_response(event.message)
                
            elif event.type == BridgeEventType.ERROR:
                error_panel = self._error_panel_for_message(event.message)
                error_panel.log_system(f"ERROR: {event.message}")
                self.query_one("#continuous-panel", ContinuousKeyencePanel).log_data(
                    f"ERROR: {event.message}"
                )

            elif event.type == BridgeEventType.SYSTEM:
                self.query_one("#spc-coms-panel", SpcComsPanel).log_system(
                    event.message
                )

            elif event.type == BridgeEventType.STATUS_CHANGED:
                pass

        self._refresh_all_panels()

    def _error_panel_for_message(self, message: str) -> CommonComsPanel:
        normalized = message.upper()

        if "SPC" in normalized:
            return self.query_one("#spc-coms-panel", SpcComsPanel)

        if "KEYENCE" in normalized or "STREAM" in normalized or "READ" in normalized:
            return self.query_one("#keyence-coms-panel", KeyenceComsPanel)

        return self.query_one("#spc-coms-panel", SpcComsPanel)
                
    def _refresh_all_panels(self) -> None:
        state = self.controller.state

        self.query_one("#status-column", StatusColumn).set_state(state)

        spc_coms_panel = self.query_one("#spc-coms-panel", SpcComsPanel)
        spc_coms_panel.set_port(state.spc.port)
        spc_coms_panel.set_connected(state.spc.connected)

        keyence_coms_panel = self.query_one("#keyence-coms-panel", KeyenceComsPanel)
        keyence_coms_panel.set_port(state.keyence.port)
        keyence_coms_panel.set_connected(state.keyence.connected)

        control_bar = self.query_one("#controls", ControlBar)
        control_bar.set_stream_enabled(state.streaming)
        control_bar.set_continuous_visible(state.continuous_visible)
        control_bar.set_simulator_enabled(state.use_simulator)
        control_bar.set_status_visible(self.show_status)
        control_bar.set_spc_coms_visible(self.show_spc_coms)
        control_bar.set_keyence_coms_visible(self.show_keyence_coms)
        control_bar.set_spc_docs_visible(self.show_spc_docs)

        docs_panel = self.query_one("#spc-docs-panel", SpcCommandDocsPanel)
        docs_panel.set_commands(self.controller.spc_commands.describe_commands())

        continuous_panel = self.query_one("#continuous-panel", ContinuousKeyencePanel)
        continuous_panel.set_tracker_sources(
            {
                registry: (
                    self.controller.height_trackers.is_active(registry),
                    self.controller.height_trackers.values(registry),
                )
                for registry in self.controller.height_trackers.registries()
            }
        )
        continuous_panel.set_class(self.show_continuous, "visible")
        docs_panel.set_class(not self.show_spc_docs, "hidden")

    def on_device_status_panel_port_changed(
        self,
        message: DeviceStatusPanel.PortChanged,
    ) -> None:
        self._apply_ports_from_ui()
        self._drain_controller_events()

    def on_device_status_panel_setting_changed(
        self,
        message: DeviceStatusPanel.SettingChanged,
    ) -> None:
        self._apply_ports_from_ui()
        self._drain_controller_events()
