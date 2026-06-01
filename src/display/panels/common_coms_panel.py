"""Reusable communications panel base class.

Owns:
- TX/RX visibility toggles
- RAW/comment display mode
- port label
- timestamped logging
- command comments/descriptions
- command send hook
- received-data hook
- terminal-style command typing
- disconnected command blocking

Child classes only provide:
- title
- id prefix
- default filter states
- known command descriptions
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import textwrap
from typing import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click, Key
from textual.message import Message
from textual.widgets import Label, RichLog, Static


CommandCommentFormatter = Callable[[re.Match[str]], str]


@dataclass(frozen=True)
class CommandComment:
    """
    Defines a known command and the human-readable explanation for it.

    pattern:
        Either an exact command string, like "MS,3,2",
        or a regex pattern if regex=True.

    comment:
        Either a plain string or a function that receives the regex match.

    regex:
        False = exact string match.
        True = regex match.
    """

    pattern: str
    comment: str | CommandCommentFormatter
    regex: bool = False


@dataclass(frozen=True)
class ComsLogEntry:
    timestamp: str
    direction: str
    message: str


class CommonComsPanel(Vertical):
    NOT_CONNECTED_RESPONSE = "WARNING: NOT_CONNECTED"
    NOT_CONNECTED_COMMENT = "Device is not connected"
    UNKNOWN_COMMENT = "Unknown/undocumented command"

    class CommandSubmitted(Message):
        """
        Message emitted when this panel requests that a command be sent.

        The controller/app can listen for this and actually write to serial.
        """

        def __init__(self, command: str, source: "CommonComsPanel") -> None:
            super().__init__()
            self.command = command
            self.source = source

    def __init__(
        self,
        *,
        title: str,
        id_prefix: str,
        command_comments: list[CommandComment],
        default_show_tx: bool = True,
        default_show_rx: bool = True,
        default_show_time: bool = True,
        default_wrap: bool = True,
        default_raw: bool = True,
        default_connected: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        if not command_comments:
            raise ValueError(
                f"{type(self).__name__} must define at least one command comment."
            )

        self.panel_title = title
        self.id_prefix = id_prefix

        self.show_tx = default_show_tx
        self.show_rx = default_show_rx
        self.show_time = default_show_time
        self.wrap_text = default_wrap
        self.raw_mode = default_raw

        self.command_comments = command_comments

        self.can_focus = True
        self.command_buffer = ""
        self.command_history: list[str] = []
        self.history_index: int | None = None

        self.connected = default_connected
        self.log_entries: list[ComsLogEntry] = []
        self.max_log_entries = 500

    @property
    def port_id(self) -> str:
        return f"{self.id_prefix}-coms-port"

    @property
    def tx_toggle_id(self) -> str:
        return f"{self.id_prefix}-show-tx"

    @property
    def rx_toggle_id(self) -> str:
        return f"{self.id_prefix}-show-rx"

    @property
    def raw_toggle_id(self) -> str:
        return f"{self.id_prefix}-show-raw"

    @property
    def time_toggle_id(self) -> str:
        return f"{self.id_prefix}-show-time"

    @property
    def wrap_toggle_id(self) -> str:
        return f"{self.id_prefix}-wrap"

    @property
    def log_id(self) -> str:
        return f"{self.id_prefix}-coms-log"

    @property
    def prompt_id(self) -> str:
        return f"{self.id_prefix}-command-prompt"

    def compose(self) -> ComposeResult:
        self.add_class("panel")

        with Horizontal(classes="panel-title-row"):
            yield Label(self.panel_title, classes="panel-title")
            yield Static("", id=self.port_id, classes="panel-title-port")

            yield Static(
                "RAW",
                id=self.raw_toggle_id,
                classes=self._toggle_classes(
                    self.raw_mode,
                    extra_class="coms-filter-raw",
                ),
            )

            yield Static(
                "TIME",
                id=self.time_toggle_id,
                classes=self._toggle_classes(
                    self.show_time,
                    extra_class="coms-filter-time",
                ),
            )

            yield Static(
                "WRAP",
                id=self.wrap_toggle_id,
                classes=self._toggle_classes(
                    self.wrap_text,
                    extra_class="coms-filter-wrap",
                ),
            )

            yield Static(
                "RX",
                id=self.rx_toggle_id,
                classes=self._toggle_classes(self.show_rx),
            )

            yield Static(
                "TX",
                id=self.tx_toggle_id,
                classes=self._toggle_classes(self.show_tx),
            )

        with Vertical(classes="coms-terminal"):
            yield RichLog(
                id=self.log_id,
                wrap=self.wrap_text,
                auto_scroll=True,
                max_lines=500,
                classes="coms-log",
            )

            yield Static(
                "> ",
                id=self.prompt_id,
                classes="coms-command-prompt",
            )

    def on_click(self, event: Click) -> None:
        self.focus()

        widget_id = event.widget.id if event.widget else None

        if widget_id == self.tx_toggle_id:
            self.show_tx = not self.show_tx
            self._set_filter_visual(f"#{self.tx_toggle_id}", self.show_tx)
            self._render_log()
            event.stop()
            return

        if widget_id == self.rx_toggle_id:
            self.show_rx = not self.show_rx
            self._set_filter_visual(f"#{self.rx_toggle_id}", self.show_rx)
            self._render_log()
            event.stop()
            return

        if widget_id == self.raw_toggle_id:
            self.raw_mode = not self.raw_mode
            self._set_filter_visual(f"#{self.raw_toggle_id}", self.raw_mode)
            self._render_log()
            event.stop()
            return

        if widget_id == self.time_toggle_id:
            self.show_time = not self.show_time
            self._set_filter_visual(f"#{self.time_toggle_id}", self.show_time)
            self._render_log()
            event.stop()
            return

        if widget_id == self.wrap_toggle_id:
            self.wrap_text = not self.wrap_text
            self._set_filter_visual(f"#{self.wrap_toggle_id}", self.wrap_text)
            self.query_one(f"#{self.log_id}", RichLog).wrap = self.wrap_text
            self._render_log()
            event.stop()
            return

    def on_key(self, event: Key) -> None:
        if event.key == "enter":
            command = self.command_buffer.strip()

            if command:
                self._add_command_to_history(command)
                self.send_command(command)

            self.command_buffer = ""
            self.history_index = None
            self._render_prompt()
            event.stop()
            return

        if event.key == "up":
            self._move_history(-1)
            event.stop()
            return

        if event.key == "down":
            self._move_history(1)
            event.stop()
            return

        if event.key == "backspace":
            self.history_index = None
            self.command_buffer = self.command_buffer[:-1]
            self._render_prompt()
            event.stop()
            return

        if event.key == "escape":
            self.command_buffer = ""
            self.history_index = None
            self._render_prompt()
            event.stop()
            return

        if event.key == "space":
            self.history_index = None
            self.command_buffer += " "
            self._render_prompt()
            event.stop()
            return

        if event.character and len(event.character) == 1:
            self.history_index = None
            self.command_buffer += event.character
            self._render_prompt()
            event.stop()
            return

    def set_port(self, port: str) -> None:
        self.query_one(f"#{self.port_id}", Static).update(f"({port})")

    def set_connected(self, connected: bool) -> None:
        self.connected = connected

    def send_command(self, command: str) -> None:
        """
        Preferred way for UI/controller code to request a command send.

        This:
        1. handles local panel commands like CLS/CLEAR
        2. logs the outgoing command
        3. refuses sending if not connected
        4. emits a CommandSubmitted message if connected
        5. gives child classes a hook if connected
        """

        command = command.strip()

        if not command:
            return

        if command.upper() in {"CLS", "CLEAR"}:
            self.clear_log()
            return

        self.log_sent(command)

        if not self.connected:
            self.log_system(self.NOT_CONNECTED_RESPONSE)
            return

        self.post_message(self.CommandSubmitted(command, self))
        self.after_command_submitted(command)
        
    def receive_data(self, message: str) -> None:
        """
        Preferred way to pass received serial data into the panel.

        This:
        1. logs the incoming message
        2. gives child classes a hook
        """

        message = message.strip()

        if not message:
            return

        self.log_received(message)
        self.after_data_received(message)

    def log_sent(self, message: str) -> None:
        if self.show_tx:
            self._log("TX", message)

    def log_received(self, message: str) -> None:
        if self.show_rx:
            self._log("RX", message)

    def log_system(self, message: str) -> None:
        self._log("SYS", message)

    def clear_log(self) -> None:
        self.log_entries.clear()
        self.query_one(f"#{self.log_id}", RichLog).clear()

    def log_command(self, message: str) -> None:
        """
        Backwards-compatible method.

        Old code can still call log_command(...), but command logs should be TX.
        """

        self.log_sent(message)

    def after_command_submitted(self, command: str) -> None:
        """
        Optional child hook.

        Override this if a child panel needs to react after a command is submitted.
        Do not put serial-writing here unless you intentionally want the panel
        coupled to the serial layer.
        """

    def after_data_received(self, message: str) -> None:
        """
        Optional child hook.

        Override this if a child panel needs to parse received data.
        """

    def describe_command(self, command: str) -> str | None:
        raw_command = command.strip()

        if raw_command == self.NOT_CONNECTED_RESPONSE:
            return self.NOT_CONNECTED_COMMENT

        command = raw_command.upper()

        for item in self.command_comments:
            if item.regex:
                match = re.fullmatch(item.pattern, command)
                if match is None:
                    continue

                if callable(item.comment):
                    return item.comment(match)

                return item.comment

            if command == item.pattern.upper():
                if callable(item.comment):
                    raise TypeError("Callable command comments require regex=True.")

                return item.comment

        return None

    def _format_log_message(self, direction: str, message: str) -> str:
        if direction == "SYS":
            return f"{direction:<3} | {message}"

        comment = self.describe_command(message)

        if comment is None:
            comment = self.UNKNOWN_COMMENT

        if self.raw_mode:
            return f"{direction:<3} | {message}\t# {comment}"

        return f"{direction:<3} | {comment}"

    def _log(self, direction: str, message: str) -> None:
        entry = ComsLogEntry(
            timestamp=self._time(),
            direction=direction,
            message=message,
        )
        self.log_entries.append(entry)

        if len(self.log_entries) > self.max_log_entries:
            self.log_entries = self.log_entries[-self.max_log_entries :]

        if self._entry_visible(entry):
            self._write_entry(entry)

    def _render_log(self) -> None:
        log = self.query_one(f"#{self.log_id}", RichLog)
        log.clear()

        for entry in self.log_entries:
            if self._entry_visible(entry):
                self._write_entry(entry)

    def _write_entry(self, entry: ComsLogEntry) -> None:
        display = self._wrap_display_text(
            self._format_log_message(entry.direction, entry.message)
        )
        prefix = f"[{entry.timestamp}] " if self.show_time else ""
        style = "bold white on #7a2020" if self._entry_is_error(entry) else ""

        self.query_one(f"#{self.log_id}", RichLog).write(
            Text(f"{prefix}{display}", style=style)
        )

    def _entry_visible(self, entry: ComsLogEntry) -> bool:
        if entry.direction == "TX":
            return self.show_tx

        if entry.direction == "RX":
            return self.show_rx

        return True

    def _entry_is_error(self, entry: ComsLogEntry) -> bool:
        message = entry.message.strip().upper()

        if entry.direction == "SYS" and "ERROR" in message:
            return True

        return (
            message.startswith("ERROR")
            or message.startswith("ER,")
            or " FAILED" in message
            or "FAILURE" in message
        )

    def _wrap_display_text(self, display: str) -> str:
        if not self.wrap_text:
            return display

        log = self.query_one(f"#{self.log_id}", RichLog)
        width = max(20, log.size.width - 4)

        return textwrap.fill(
            display,
            width=width,
            subsequent_indent="    ",
            break_long_words=False,
            break_on_hyphens=False,
        )

    def _render_prompt(self) -> None:
        self.query_one(f"#{self.prompt_id}", Static).update(
            f"> {self.command_buffer}"
        )

    def _add_command_to_history(self, command: str) -> None:
        if self.command_history and self.command_history[-1] == command:
            return

        self.command_history.append(command)

        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]

    def _move_history(self, direction: int) -> None:
        if not self.command_history:
            return

        if self.history_index is None:
            self.history_index = len(self.command_history)

        self.history_index += direction
        self.history_index = max(0, min(len(self.command_history), self.history_index))

        if self.history_index == len(self.command_history):
            self.command_buffer = ""
        else:
            self.command_buffer = self.command_history[self.history_index]

        self._render_prompt()

    def _set_filter_visual(self, selector: str, enabled: bool) -> None:
        widget = self.query_one(selector, Static)
        widget.set_class(enabled, "enabled")
        widget.set_class(not enabled, "disabled")

    @staticmethod
    def _toggle_classes(enabled: bool, extra_class: str = "") -> str:
        state_class = "enabled" if enabled else "disabled"

        classes = ["coms-filter-mini", state_class]

        if extra_class:
            classes.append(extra_class)

        return " ".join(classes)

    @staticmethod
    def _time() -> str:
        return datetime.now().strftime("%H:%M:%S")
