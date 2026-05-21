"""SPC request command registry.

SPC sends line-oriented requests to the bridge. This module owns the list of
recognized request names, their descriptions, aliases, and dispatch handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

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
        ]
    )


def parse_spc_message(message: str) -> ParsedSpcMessage | None:
    raw = message.strip()

    if not raw:
        return None

    parts = raw.split()
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
