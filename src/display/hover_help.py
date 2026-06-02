"""Reusable hover help utilities for the Textual UI."""

from __future__ import annotations

from textual.dom import DOMNode
from textual.widget import Widget
from textual.widgets import Static


HELP_TEXT_ATTR = "_bridge_hover_help_text"
DEFAULT_HELP_TEXT = (
    "q: Quit  |  c: Connect  |  h: Height  |  d: Docs  |  r: Read  |  "
    "Hover over a control for help"
)


class HelpBar(Static):
    def compose_help(self, text: str | None = None) -> None:
        self.update(text or DEFAULT_HELP_TEXT)


def set_hover_help(widget: Widget, text: str) -> None:
    setattr(widget, HELP_TEXT_ATTR, text)
    widget.tooltip = None


def get_hover_help(node: DOMNode | None) -> str | None:
    current = node

    while current is not None:
        help_text = getattr(current, HELP_TEXT_ATTR, None)

        if help_text:
            return help_text

        current = getattr(current, "parent", None)

    return None
