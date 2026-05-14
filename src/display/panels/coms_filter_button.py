"""Small reusable ON/OFF filter button for coms panels."""

from __future__ import annotations

from textual.widgets import Button


class ComsFilterButton(Button):
    def __init__(
        self,
        label_prefix: str,
        *,
        button_id: str,
        default_enabled: bool = True,
    ) -> None:
        super().__init__("", id=button_id, classes="coms-filter-button")
        self.label_prefix = label_prefix
        self.enabled = default_enabled

    def on_mount(self) -> None:
        self.set_enabled(self.enabled)

    def toggle_enabled(self) -> bool:
        self.set_enabled(not self.enabled)
        return self.enabled

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.label = f"{self.label_prefix}: {'ON' if enabled else 'OFF'}"
        self.set_class(enabled, "coms-filter-on")
        self.set_class(not enabled, "coms-filter-off")