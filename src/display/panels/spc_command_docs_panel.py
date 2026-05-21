"""Panel that documents accepted SPC commands from the live command registry."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Label, Static

from src.bridge.spc_commands import SpcCommand


class SpcCommandDocsPanel(Vertical):
    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield Label("SPC Command Docs", classes="panel-title")
        with VerticalScroll(id="spc-command-docs-scroll"):
            yield Static("", id="spc-command-docs")

    def set_commands(self, commands: list[SpcCommand]) -> None:
        rows: list[str] = []

        for command in commands:
            rows.append(command.name)
            rows.append(f"  {command.description}")

            if command.aliases:
                rows.append(f"  Aliases: {', '.join(command.aliases)}")

            if command.reply_description:
                rows.append(f"  Reply: {command.reply_description}")

            rows.append("")

        self.query_one("#spc-command-docs", Static).update("\n".join(rows).rstrip())
