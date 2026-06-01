"""Main Textual UI orchestrator.

BridgeTuiApp composes the display/status/control layer. It does not own hardware
behavior directly; it calls BridgeController, drains controller events, and
routes those events into panels such as SPC Coms, Keyence Coms, status panels,
the SPC Docs panel, and the height graph.

The app also installs footer hover-help. Floating tooltips are disabled; help is
shown in the footer bar so the dense terminal UI stays readable.
"""

from __future__ import annotations

import time

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import MouseMove
from textual.reactive import reactive
from textual.widgets import Header

from src.bridge.program_logger import ProgramLogger
from src.display.panels.common_coms_panel import CommonComsPanel
from src.display.panels.device_status_panel import DeviceStatusPanel
from src.bridge.bridge_controller import BridgeController
from src.bridge.bridge_events import BridgeEventType
from src.display.hover_help import DEFAULT_HELP_TEXT, HelpBar, get_hover_help
from src.display.hover_help_registry import install_hover_help
from src.display.panels.height_data_panel import HeightDataPanel
from src.display.panels.control_bar import ControlBar
from src.display.panels.keyence_coms_panel import KeyenceComsPanel
from src.display.panels.misc_state_panel import MiscStatePanel
from src.display.panels.spc_command_docs_panel import SpcCommandDocsPanel
from src.display.panels.spc_coms_panel import SpcComsPanel
from src.display.panels.status_column import StatusColumn


class BridgeTuiApp(App):
    CSS_PATH = "terminal_app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("h", "toggle_height_data", "Toggle height panel"),
        ("c", "connect", "Connect"),
        ("d", "toggle_spc_docs", "Toggle SPC docs"),
        ("s", "toggle_simulator", "Toggle simulator"),
        ("r", "read_once", "Read once"),
    ]

    show_height_data: reactive[bool] = reactive(False)
    show_status: reactive[bool] = reactive(True)
    show_spc_coms: reactive[bool] = reactive(True)
    show_keyence_coms: reactive[bool] = reactive(True)
    show_spc_docs: reactive[bool] = reactive(False)

    def __init__(self, controller: BridgeController) -> None:
        super().__init__()
        self.controller = controller
        self._current_help_text = DEFAULT_HELP_TEXT
        self.program_logger = ProgramLogger(
            keep_count=controller.config.log_keep_count,
        )
        self._last_height_tracker_refresh_at = 0.0
        self._last_keyence_stream_log_at = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main"):
            with Horizontal(id="content-row"):
                with Vertical(id="left-column"):
                    with Horizontal(id="coms-row"):
                        yield SpcCommandDocsPanel(id="spc-docs-panel")
                        yield SpcComsPanel(id="spc-coms-panel")
                        yield KeyenceComsPanel(id="keyence-coms-panel")

                    yield HeightDataPanel(id="height-data-panel")

                yield StatusColumn(id="status-column")

            yield ControlBar(id="controls")

        yield HelpBar(DEFAULT_HELP_TEXT, id="help-footer")
                
    def on_mount(self) -> None:
        self.title = "SpiiPlusSPC / Keyence Bridge Interface"
        self.sub_title = "AMRL Gen2 Laser System"

        self._refresh_all_panels()
        self.program_logger.start()
        self._drain_controller_events()
        install_hover_help(self)

        self.set_interval(0.1, self._tick)

    def on_unmount(self) -> None:
        self.program_logger.close()

    def on_mouse_move(self, event: MouseMove) -> None:
        help_text = get_hover_help(event.widget) or DEFAULT_HELP_TEXT

        if help_text == self._current_help_text:
            return

        self._current_help_text = help_text
        self.query_one("#help-footer", HelpBar).compose_help(help_text)

    def on_control_bar_close_requested(self, _: ControlBar.CloseRequested) -> None:
        self.controller.close()
        self.program_logger.close()
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
        
    def on_control_bar_height_data_visibility_changed(
        self,
        message: ControlBar.HeightDataVisibilityChanged,
    ) -> None:
        self._set_height_data_panel_visible(message.visible)

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

    def on_misc_state_panel_setting_changed(
        self,
        message: MiscStatePanel.SettingChanged,
    ) -> None:
        if message.setting == "log_keep_count":
            self.controller.set_log_keep_count(message.value)
            self.program_logger.set_keep_count(
                self.controller.state.log_keep_count
            )
            self._drain_controller_events()

    def on_height_data_panel_export_completed(
        self,
        message: HeightDataPanel.ExportCompleted,
    ) -> None:
        keyence_panel = self.query_one("#keyence-coms-panel", KeyenceComsPanel)

        if message.error is not None:
            keyence_panel.log_system(f"CSV export failed: {message.error}")
            return

        keyence_panel.log_system(f"CSV exported: {message.path}")

    def on_height_data_panel_next_layer_requested(
        self,
        message: HeightDataPanel.NextLayerRequested,
    ) -> None:
        if message.registry is None:
            self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_system(
                "NEXT_LAYER requires a selected tracking registry"
            )
            return

        try:
            layer_index = self.controller.next_tracking_layer(message.registry)
        except Exception as error:
            self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_system(
                f"NEXT_LAYER failed: {error}"
            )
            return

        self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_system(
            f"Registry {message.registry} advanced to layer {layer_index}"
        )
        self._drain_controller_events()

    def on_height_data_panel_create_registry_requested(
        self,
        message: HeightDataPanel.CreateRegistryRequested,
    ) -> None:
        try:
            registry = self.controller.ensure_tracking_registry(message.registry)
        except Exception as error:
            self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_system(
                f"Register creation failed: {error}"
            )
            return

        self._drain_controller_events()
        height_data_panel = self.query_one("#height-data-panel", HeightDataPanel)
        height_data_panel.select_registry(registry)

    def on_height_data_panel_toggle_registry_requested(
        self,
        message: HeightDataPanel.ToggleRegistryRequested,
    ) -> None:
        if message.registry is None:
            self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_system(
                "START/STOP requires a selected tracking registry"
            )
            return

        try:
            if message.enable:
                self.controller.start_tracking_registry(message.registry)
            else:
                self.controller.stop_tracking_registry(message.registry)
        except Exception as error:
            self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_system(
                f"START/STOP failed: {error}"
            )
            return

        self._drain_controller_events()

    def on_height_data_panel_clear_registry_requested(
        self,
        message: HeightDataPanel.ClearRegistryRequested,
    ) -> None:
        if message.registry is None:
            self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_system(
                "CLEAR requires a selected tracking registry"
            )
            return

        try:
            if message.layer == "ALL":
                self.controller.clear_tracking_registry(message.registry)
            else:
                self.controller.clear_tracking_registry_layer(
                    message.registry,
                    int(message.layer),
                )
        except Exception as error:
            self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_system(
                f"CLEAR failed: {error}"
            )
            return

        self._drain_controller_events()

    def watch_show_height_data(self, show: bool) -> None:
        if show:
            self._last_height_tracker_refresh_at = 0.0

        self.query_one("#height-data-panel", HeightDataPanel).set_class(
            show,
            "visible",
        )

        control_bar = self.query_one("#controls", ControlBar)
        control_bar.set_height_data_visible(show)

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

    def _set_height_data_panel_visible(self, visible: bool) -> None:
        self.show_height_data = visible
        self.controller.set_height_data_visible(visible)

        control_bar = self.query_one("#controls", ControlBar)
        control_bar.set_height_data_visible(visible)

        self._drain_controller_events()

    def action_toggle_height_data(self) -> None:
        self._set_height_data_panel_visible(not self.show_height_data)

    def action_toggle_spc_docs(self) -> None:
        self.show_spc_docs = not self.show_spc_docs

    def action_connect(self) -> None:
        self._apply_ports_from_ui()
        self.controller.connect()
        self._drain_controller_events()

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
        did_receive_event = False

        for event in self.controller.drain_events():
            did_receive_event = True

            if event.type == BridgeEventType.SPC_RECEIVED:
                self.program_logger.write("RX", "SPC", event.message)
                self.query_one("#spc-coms-panel", SpcComsPanel).receive_data(
                    event.message
                )

            elif event.type == BridgeEventType.SPC_SENT:
                self.program_logger.write("TX", "SPC", event.message)
                self.query_one("#spc-coms-panel", SpcComsPanel).log_sent(
                    event.message
                )

            elif event.type == BridgeEventType.KEYENCE_SENT:
                self.program_logger.write("TX", "KEYENCE", event.message)
                self.query_one("#keyence-coms-panel", KeyenceComsPanel).log_sent(
                    event.message
                )

            elif event.type == BridgeEventType.KEYENCE_RECEIVED:
                self.program_logger.write("RX", "KEYENCE", event.message)
                self._log_keyence_received(event.message)

                height_data_panel = self.query_one("#height-data-panel", HeightDataPanel)
                height_data_panel.log_data(event.message)
                height_data_panel.add_keyence_response(event.message)
                
            elif event.type == BridgeEventType.ERROR:
                self.program_logger.write("ERROR", "SYSTEM", event.message)
                error_panel = self._error_panel_for_message(event.message)
                error_panel.log_system(f"ERROR: {event.message}")
                self.query_one("#height-data-panel", HeightDataPanel).log_data(
                    f"ERROR: {event.message}"
                )

            elif event.type == BridgeEventType.SYSTEM:
                self.program_logger.write("SYS", "SYSTEM", event.message)
                self.query_one("#spc-coms-panel", SpcComsPanel).log_system(
                    event.message
                )

            elif event.type == BridgeEventType.STATUS_CHANGED:
                pass

        if did_receive_event:
            self._refresh_all_panels()

    def _log_keyence_received(self, message: str) -> None:
        keyence_panel = self.query_one("#keyence-coms-panel", KeyenceComsPanel)

        if not self.controller.state.streaming:
            keyence_panel.log_received(message)
            return

        if not keyence_panel.show_rx:
            return

        now = time.monotonic()

        if now - self._last_keyence_stream_log_at < 0.25:
            return

        self._last_keyence_stream_log_at = now
        keyence_panel.log_received(message)

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
        control_bar.set_height_data_visible(state.height_data_visible)
        control_bar.set_simulator_enabled(state.use_simulator)
        control_bar.set_status_visible(self.show_status)
        control_bar.set_spc_coms_visible(self.show_spc_coms)
        control_bar.set_keyence_coms_visible(self.show_keyence_coms)
        control_bar.set_spc_docs_visible(self.show_spc_docs)

        docs_panel = self.query_one("#spc-docs-panel", SpcCommandDocsPanel)
        docs_panel.set_commands(self.controller.spc_commands.describe_commands())

        height_data_panel = self.query_one("#height-data-panel", HeightDataPanel)
        height_data_panel.set_class(self.show_height_data, "visible")

        if self.show_height_data and self._should_refresh_height_tracker_sources():
            height_data_panel.set_tracker_sources(
                {
                    registry: (
                        self.controller.height_trackers.is_active(registry),
                        self.controller.height_trackers.is_paused(registry),
                        self.controller.height_trackers.current_layer(registry),
                        self.controller.height_trackers.layers(registry),
                        self.controller.height_trackers.count(registry),
                        self.controller.height_trackers.minimum(registry),
                        self.controller.height_trackers.maximum(registry),
                        self.controller.height_trackers.average(registry),
                    )
                    for registry in self.controller.height_trackers.registries()
                }
            )

        docs_panel.set_class(not self.show_spc_docs, "hidden")

    def _should_refresh_height_tracker_sources(self) -> bool:
        if not self.controller.state.streaming:
            self._last_height_tracker_refresh_at = time.monotonic()
            return True

        now = time.monotonic()

        if now - self._last_height_tracker_refresh_at < 0.25:
            return False

        self._last_height_tracker_refresh_at = now
        return True

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
