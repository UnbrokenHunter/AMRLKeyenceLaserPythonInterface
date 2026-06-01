"""Panel that displays miscellaneous bridge state."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label, Static

from src.bridge.bridge_state import BridgeViewState


class MiscStatePanel(Vertical):
    class SettingChanged(Message):
        def __init__(self, setting: str, value: str) -> None:
            super().__init__()
            self.setting = setting
            self.value = value

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.log_keep_count = "25"
        self.export_keep_count = "25"
        self.force_log_keep_refresh = False
        self.force_export_keep_refresh = False

    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield Label("Bridge State", classes="panel-title")
        yield Static("", id="misc-state")
        with Horizontal(classes="port-row"):
            yield Label(
                "Logs",
                id="misc-log_keep_count-label",
                classes="field-label port-label",
            )
            with Horizontal(classes="port-input-shell"):
                yield Input(
                    value=self.log_keep_count,
                    id="misc-log_keep_count",
                    classes="port-input",
                    compact=True,
                )
        with Horizontal(classes="port-row"):
            yield Label(
                "Exports",
                id="misc-export_keep_count-label",
                classes="field-label port-label",
            )
            with Horizontal(classes="port-input-shell"):
                yield Input(
                    value=self.export_keep_count,
                    id="misc-export_keep_count",
                    classes="port-input",
                    compact=True,
                )

        yield Static("", classes="status-line")
        yield Static("Error: --", id="misc-error")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "misc-log_keep_count":
            self.force_log_keep_refresh = True
            self._commit_log_keep_count(event.input.value)
            event.input.blur()
            event.stop()

        if event.input.id == "misc-export_keep_count":
            self.force_export_keep_refresh = True
            self._commit_export_keep_count(event.input.value)
            event.input.blur()
            event.stop()

    def on_input_blurred(self, event: Input.Blurred) -> None:
        if event.input.id == "misc-log_keep_count":
            self._commit_log_keep_count(event.input.value)
            event.stop()

        if event.input.id == "misc-export_keep_count":
            self._commit_export_keep_count(event.input.value)
            event.stop()

    def set_state(self, state: BridgeViewState) -> None:
        self.query_one("#misc-state", Static).update(
            Text(
                f"Simulator: {'ON' if state.use_simulator else 'OFF'}\n"
                f"Streaming: {'ON' if state.streaming else 'OFF'}\n"
                f"Height panel: {'shown' if state.height_data_visible else 'hidden'}\n"
                f"Keyence OUT: {state.keyence_out_no}\n"
                f"SPC baud: {state.spc_baudrate}\n"
                f"SPC line: {state.spc_line_ending}\n"
                f"Keep logs: {state.log_keep_count}\n"
                f"Keep exports: {state.export_keep_count}\n"
                f"SPC RX: {state.spc_rx_count}\n"
                f"SPC TX: {state.spc_tx_count}\n"
                f"Keyence TX: {state.keyence_tx_count}\n"
                f"Keyence RX: {state.keyence_rx_count}"
            )
        )

        self.log_keep_count = str(state.log_keep_count)
        log_keep_input = self.query_one("#misc-log_keep_count", Input)

        if self.force_log_keep_refresh or not log_keep_input.has_focus:
            log_keep_input.value = self.log_keep_count
            self.force_log_keep_refresh = False

        self.export_keep_count = str(state.export_keep_count)
        export_keep_input = self.query_one("#misc-export_keep_count", Input)

        if self.force_export_keep_refresh or not export_keep_input.has_focus:
            export_keep_input.value = self.export_keep_count
            self.force_export_keep_refresh = False

        error_line = self.query_one("#misc-error", Static)
        has_error = bool(state.last_error)
        error_line.update(f"Error: {self._format_error(state.last_error)}")
        error_line.set_class(has_error, "error-active")

    def _commit_log_keep_count(self, value: str) -> None:
        value = value.strip()

        if not value:
            self.query_one("#misc-log_keep_count", Input).value = self.log_keep_count
            return

        self.log_keep_count = value
        self.post_message(self.SettingChanged("log_keep_count", value))

    def _commit_export_keep_count(self, value: str) -> None:
        value = value.strip()

        if not value:
            self.query_one("#misc-export_keep_count", Input).value = (
                self.export_keep_count
            )
            return

        self.export_keep_count = value
        self.post_message(self.SettingChanged("export_keep_count", value))

    @staticmethod
    def _format_error(error: str | None) -> str:
        if not error:
            return "--"

        error = error.replace("\n", " ")

        max_len = 120
        if len(error) > max_len:
            return error[:max_len] + "..."

        return error
