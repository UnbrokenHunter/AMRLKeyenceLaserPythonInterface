"""SPC request command registry.

SPC sends line-oriented requests to the bridge. This module owns the list of
recognized request names, their descriptions, aliases, and dispatch handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class SpcCommand:
    name: str
    description: str
    handler: SpcCommandHandler
    aliases: tuple[str, ...] = ()
    reply_description: str = ""

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
                reply_description="PONG",
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
                name="START_STREAM",
                description="Start Keyence automatic transmission.",
                reply_description="OK or ERROR ...",
                handler=_handle_start_stream,
            ),
            SpcCommand(
                name="STOP_STREAM",
                description="Stop Keyence automatic transmission.",
                reply_description="OK or ERROR ...",
                handler=_handle_stop_stream,
            ),
            SpcCommand(
                name="START_TRACKING",
                description="Start appending new valid Keyence heights to a named tracking registry.",
                reply_description="OK TRACKING_STARTED <registry> COUNT=<n>",
                handler=_handle_start_tracking,
            ),
            SpcCommand(
                name="STOP_TRACKING",
                description="Stop appending new heights to a named tracking registry.",
                reply_description="OK TRACKING_STOPPED <registry> COUNT=<n>",
                handler=_handle_stop_tracking,
            ),
            SpcCommand(
                name="CLEAR_TRACKING",
                description="Clear all samples from a named tracking registry.",
                reply_description="OK TRACKING_CLEARED <registry>",
                handler=_handle_clear_tracking,
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
    name = normalize_command_name(parts[0])
    args = tuple(parts[1:])

    return ParsedSpcMessage(raw=message, name=name, args=args)


def normalize_command_name(name: str) -> str:
    return name.strip().upper()


def _handle_ping(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    return "PONG"


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
    count = context.controller.height_trackers.count(registry)
    return f"OK TRACKING_STARTED {registry} COUNT={count}"


def _handle_stop_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    context.controller.height_trackers.stop(registry)
    count = context.controller.height_trackers.count(registry)
    return f"OK TRACKING_STOPPED {registry} COUNT={count}"


def _handle_clear_tracking(
    context: SpcCommandContext,
    parsed: ParsedSpcMessage,
) -> str:
    registry = _tracking_registry_arg(parsed)
    context.controller.height_trackers.clear(registry)
    return f"OK TRACKING_CLEARED {registry}"


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
