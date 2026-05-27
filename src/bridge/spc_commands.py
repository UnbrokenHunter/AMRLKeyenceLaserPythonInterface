"""SPC request command registry.

SPC sends line-oriented requests to the bridge through the virtual serial link.
This module is the source of truth for accepted SPC commands, their aliases,
their descriptions, their reply descriptions, and their handler functions.

The in-app SPC Docs panel reads from this registry. When a command is added or
changed here, the UI documentation changes with it. Duplicate command names or
aliases raise an error when the registry is built so ambiguous SPC messages do
not silently dispatch to the wrong handler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

from src.bridge.height_tracking import normalize_registry_name

if TYPE_CHECKING:
    from src.bridge.bridge_controller import BridgeController


@dataclass(frozen=True)
class ParsedSpcMessage:
    raw: str
    name: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class SpcCommandContext:
    controller: "BridgeController"


SpcCommandHandler = Callable[[SpcCommandContext, ParsedSpcMessage], str | bytes | None]
SPC_SUCCESS_STATUS = "1"
SPC_FAILURE_STATUS = "0"


@dataclass(frozen=True)
class SpcCommand:
    name: str
    description: str
    handler: SpcCommandHandler
    aliases: tuple[str, ...] = ()
    reply_description: str = ""
    failure_reply: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("SPC command name is required")

        if not self.description.strip():
            raise ValueError(f"SPC command {self.name!r} requires a description")

    @property
    def normalized_name(self) -> str:
        return normalize_command_name(self.name)

    @property
    def normalized_aliases(self) -> tuple[str, ...]:
        return tuple(normalize_command_name(alias) for alias in self.aliases)


class SpcCommandRegistry:
    def __init__(self, commands: list[SpcCommand]) -> None:
        self.commands = commands
        self._commands_by_name: dict[str, SpcCommand] = {}

        for command in commands:
            self._register_name(command.normalized_name, command)

            for alias in command.normalized_aliases:
                self._register_name(alias, command)

    def handle(
        self,
        message: str,
        context: SpcCommandContext,
    ) -> str | bytes | None:
        parsed = parse_spc_message(message)

        if parsed is None:
            return None

        command = self._commands_by_name.get(parsed.name)

        if command is None:
            return f"ERROR UNKNOWN_COMMAND {message.strip()}"

        try:
            return command.handler(context, parsed)
        except Exception as error:
            if command.failure_reply is not None:
                return command.failure_reply

            return f"ERROR {command.normalized_name} {error}"

    def describe_commands(self) -> list[SpcCommand]:
        return list(self.commands)

    def _register_name(self, name: str, command: SpcCommand) -> None:
        if not name:
            raise ValueError(f"SPC command {command.name!r} has an empty alias/name")

        existing = self._commands_by_name.get(name)

        if existing is not None:
            raise ValueError(
                f"Duplicate SPC command name/alias {name!r}: "
                f"{existing.name!r} and {command.name!r}"
            )

        self._commands_by_name[name] = command


def create_default_spc_command_registry() -> SpcCommandRegistry:
    return SpcCommandRegistry(
        commands=[
            SpcCommand(
                name="PING",
                description="Check whether the Python bridge is responding.",
                reply_description="1",
                handler=_handle_ping,
            ),
            SpcCommand(
                name="STATUS",
                description="Return current bridge, SPC peer, stream, and height state.",
                reply_description=(
                    "KEYENCE_CONNECTED=...;SPC_CONNECTED=...;STREAMING=...;HEIGHT=..."
                ),
                handler=_handle_status,
            ),
            SpcCommand(
                name="GET_LAST_HEIGHT",
                aliases=("GET_HEIGHT", "HEIGHT?"),
                description="Return the latest known Keyence height without forcing a read.",
                reply_description="Numeric height in mm, or NO_HEIGHT.",
                handler=_handle_get_height,
            ),
            SpcCommand(
                name="READ_HEIGHT",
                aliases=("READ_ONCE",),
                description="Perform a fresh averaged Keyence read and return the height.",
                reply_description="Numeric height in mm, or ERROR ...",
                handler=_handle_read_once,
            ),
            SpcCommand(
                name="GET_PROGRAM",
                aliases=("PROGRAM?", "GET_KEYENCE_PROGRAM"),
                description="Return the active Keyence program number.",
                reply_description="Numeric program number, or ERROR ...",
                handler=_handle_get_program,
            ),
            SpcCommand(
                name="SET_PROGRAM",
                aliases=("CHANGE_PROGRAM", "SET_KEYENCE_PROGRAM"),
                description="Change the active Keyence program number.",
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_set_program,
            ),
            SpcCommand(
                name="START_STREAM",
                description="Start Keyence automatic transmission.",
                reply_description="1 on success, 0 on failure.",
                handler=_handle_start_stream,
            ),
            SpcCommand(
                name="STOP_STREAM",
                description="Stop Keyence automatic transmission.",
                reply_description="1 on success, 0 on failure.",
                handler=_handle_stop_stream,
            ),
            SpcCommand(
                name="START_TRACKING",
                description="Start appending new valid Keyence heights to a named tracking registry.",
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_start_tracking,
            ),
            SpcCommand(
                name="STOP_TRACKING",
                description="Stop appending new heights to a named tracking registry.",
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_stop_tracking,
            ),
            SpcCommand(
                name="PAUSE_TRACKING",
                description=(
                    "Temporarily stop appending heights to a named tracking "
                    "registry without ending the tracking session."
                ),
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_pause_tracking,
            ),
            SpcCommand(
                name="RESUME_TRACKING",
                description="Resume appending heights to a paused tracking registry.",
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_resume_tracking,
            ),
            SpcCommand(
                name="CLEAR_TRACKING",
                description="Clear all samples from a named tracking registry.",
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_clear_tracking,
            ),
            SpcCommand(
                name="NEXT_LAYER",
                aliases=("NEXT_SCAN_LAYER",),
                description="Advance a tracking registry to a new scan layer.",
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_next_layer,
            ),
            SpcCommand(
                name="PREPARE",
                aliases=("PREPARE_TRACKING", "PREPARE_SCAN"),
                description=(
                    "Clear a tracking registry, start tracking it, and start "
                    "Keyence scanning/streaming."
                ),
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_prepare,
            ),
            SpcCommand(
                name="SAVE",
                aliases=("SAVE_TRACKING", "SAVE_SCAN"),
                description=(
                    "Stop tracking a registry, stop Keyence scanning/streaming, "
                    "and export the registry to CSV."
                ),
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_save,
            ),
            SpcCommand(
                name="SAVE_CSV",
                aliases=("EXPORT_CSV", "SAVE_TRACKING_CSV", "EXPORT_TRACKING_CSV"),
                description="Save a named tracking registry to a CSV file.",
                reply_description="1 on success, 0 on failure.",
                failure_reply=SPC_FAILURE_STATUS,
                handler=_handle_save_csv,
            ),
            SpcCommand(
                name="RETURN_TRACKING",
                description="Return all samples from a named tracking registry.",
                reply_description="TRACKING <registry> COUNT=<n> VALUES=<comma-separated-mm-values>",
                handler=_handle_return_tracking,
            ),
            SpcCommand(
                name="AVERAGE_TRACKING",
                aliases=("AVG_TRACKING",),
                description="Return the average of samples in a named tracking registry.",
                reply_description="TRACKING_AVG <registry> <value>, or NO_TRACKING_DATA <registry>",
                handler=_handle_average_tracking,
            ),
            SpcCommand(
                name="MAX_TRACKING",
                description="Return the maximum sample in a named tracking registry.",
                reply_description="TRACKING_MAX <registry> <value>, or NO_TRACKING_DATA <registry>",
                handler=_handle_max_tracking,
            ),
            SpcCommand(
                name="MIN_TRACKING",
                description="Return the minimum sample in a named tracking registry.",
                reply_description="TRACKING_MIN <registry> <value>, or NO_TRACKING_DATA <registry>",
                handler=_handle_min_tracking,
            ),
        ]
    )


def parse_spc_message(message: str) -> ParsedSpcMessage | None:
    raw = message.strip()

    if not raw:
        return None

    parts = raw.replace(",", " ").split()
    name, args = _parse_command_name_and_args(parts)

    return ParsedSpcMessage(raw=message, name=name, args=args)


def normalize_command_name(name: str) -> str:
    return name.strip().upper()


def _parse_command_name_and_args(parts: list[str]) -> tuple[str, tuple[str, ...]]:
    max_command_words = min(3, len(parts))

    for word_count in range(max_command_words, 1, -1):
        spaced_name = normalize_command_name("_".join(parts[:word_count]))
        if spaced_name in _SPC_SPACED_COMMANDS:
            return spaced_name, tuple(parts[word_count:])

    return normalize_command_name(parts[0]), tuple(parts[1:])


_SPC_SPACED_COMMANDS = {
    "GET_LAST_HEIGHT",
    "GET_HEIGHT",
    "GET_PROGRAM",
    "GET_KEYENCE_PROGRAM",
    "READ_HEIGHT",
    "READ_ONCE",
    "SET_PROGRAM",
    "CHANGE_PROGRAM",
    "SET_KEYENCE_PROGRAM",
    "START_STREAM",
    "STOP_STREAM",
    "START_TRACKING",
    "STOP_TRACKING",
    "PAUSE_TRACKING",
    "RESUME_TRACKING",
    "CLEAR_TRACKING",
    "NEXT_LAYER",
    "NEXT_SCAN_LAYER",
    "PREPARE_TRACKING",
    "PREPARE_SCAN",
    "SAVE_TRACKING",
    "SAVE_SCAN",
    "SAVE_CSV",
    "EXPORT_CSV",
    "SAVE_TRACKING_CSV",
    "EXPORT_TRACKING_CSV",
    "RETURN_TRACKING",
    "AVERAGE_TRACKING",
    "AVG_TRACKING",
    "MAX_TRACKING",
    "MIN_TRACKING",
}


def _handle_ping(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    return SPC_SUCCESS_STATUS


def _handle_status(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    controller = context.controller
    height = controller.format_latest_height_reply()

    return (
        f"KEYENCE_CONNECTED={int(controller.state.keyence.connected)};"
        f"SPC_CONNECTED={int(controller.state.spc.connected)};"
        f"STREAMING={int(controller.state.streaming)};"
        f"HEIGHT={height}"
    )


def _handle_get_height(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    return context.controller.format_latest_height_reply()


def _handle_read_once(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    return context.controller.read_height_for_spc()


def _handle_get_program(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    return context.controller.get_keyence_program_for_spc()


def _handle_set_program(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    if not parsed.args:
        return SPC_FAILURE_STATUS

    try:
        program = int(parsed.args[0])
    except ValueError:
        return SPC_FAILURE_STATUS

    return context.controller.set_keyence_program_for_spc(program)


def _handle_start_stream(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    return context.controller.start_stream_for_spc()


def _handle_stop_stream(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    return context.controller.stop_stream_for_spc()


def _handle_start_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    context.controller.height_trackers.start(registry)
    return SPC_SUCCESS_STATUS


def _handle_stop_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    context.controller.height_trackers.stop(registry)
    return SPC_SUCCESS_STATUS


def _handle_pause_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    context.controller.height_trackers.pause(registry)
    return SPC_SUCCESS_STATUS


def _handle_resume_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    context.controller.height_trackers.resume(registry)
    return SPC_SUCCESS_STATUS


def _handle_clear_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    context.controller.height_trackers.clear(registry)
    return SPC_SUCCESS_STATUS


def _handle_next_layer(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    return context.controller.next_tracking_layer_for_spc(registry)


def _handle_prepare(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    return context.controller.prepare_tracking_scan_for_spc(registry)


def _handle_save(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    return context.controller.save_tracking_scan_for_spc(registry)


def _handle_save_csv(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    return context.controller.export_tracking_csv_for_spc(registry)


def _handle_return_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    samples = context.controller.height_trackers.values(registry)
    values = ",".join(_format_height_value(sample) for sample in samples)
    return f"TRACKING {registry} COUNT={len(samples)} VALUES={values}"


def _handle_average_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    value = context.controller.height_trackers.average(registry)

    if value is None:
        return f"NO_TRACKING_DATA {registry}"

    return f"TRACKING_AVG {registry} {_format_height_value(value)}"


def _handle_max_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    value = context.controller.height_trackers.maximum(registry)

    if value is None:
        return f"NO_TRACKING_DATA {registry}"

    return f"TRACKING_MAX {registry} {_format_height_value(value)}"


def _handle_min_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    value = context.controller.height_trackers.minimum(registry)

    if value is None:
        return f"NO_TRACKING_DATA {registry}"

    return f"TRACKING_MIN {registry} {_format_height_value(value)}"


def _tracking_registry_arg(parsed: ParsedSpcMessage) -> str:
    args = list(parsed.args)

    if args and args[0].upper() == "ON":
        args.pop(0)

    if not args:
        raise ValueError("Tracking registry argument is required")

    return normalize_registry_name(args[0])


def _format_height_value(value: float) -> str:
    return f"{value:.5f}"
