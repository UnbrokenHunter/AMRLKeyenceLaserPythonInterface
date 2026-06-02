"""Bottom control bar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button


@dataclass(frozen=True)
class ActionButtonConfig:
    label: str
    button_id: str
    message_factory: Callable[[], Message]
    variant: str = "default"
    classes: str = "control-button"


@dataclass(frozen=True)
class ToggleButtonConfig:
    label: str
    button_id: str
    message_factory: Callable[[bool], Message]
    default_value: bool = False
    on_label: str | None = None
    off_label: str | None = None
    classes: str = "control-button toggle-button"


ControlConfig = ActionButtonConfig | ToggleButtonConfig


class ToggleButton(Button):
    def __init__(
        self,
        label: str,
        button_id: str,
        default_value: bool = False,
        on_label: str | None = None,
        off_label: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(label, id=button_id, **kwargs)

        self.on_label = on_label or label
        self.off_label = off_label or label
        self.enabled = default_value

    def on_mount(self) -> None:
        self.set_enabled(self.enabled)

    def toggle_enabled(self) -> bool:
        self.set_enabled(not self.enabled)
        return self.enabled

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.label = self.on_label if enabled else self.off_label
        self.set_class(enabled, "toggle-on")
        self.set_class(not enabled, "toggle-off")


class ControlBar(Horizontal):
    class CloseRequested(Message):
        pass

    class ConnectRequested(Message):
        pass

    class ReadOnceRequested(Message):
        pass

    class StreamToggleChanged(Message):
        def __init__(self, enabled: bool) -> None:
            super().__init__()
            self.enabled = enabled

    class HeightDataVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    class StatusVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    class SpcComsVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    class KeyenceComsVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    class SpcDocsVisibilityChanged(Message):
        def __init__(self, visible: bool) -> None:
            super().__init__()
            self.visible = visible

    def compose(self) -> ComposeResult:
        self.add_class("control-bar")

        for group in self._control_groups():
            with Horizontal(classes="control-group"):
                for config in group:
                    yield self._build_control(config)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id is None:
            return

        config = self._control_by_id().get(button_id)

        if config is None:
            return

        if isinstance(config, ActionButtonConfig):
            self.post_message(config.message_factory())
            return

        enabled = self.query_one(f"#{config.button_id}", ToggleButton).toggle_enabled()
        self.post_message(config.message_factory(enabled))

    def set_stream_enabled(self, enabled: bool) -> None:
        self._set_toggle_enabled("stream-toggle", enabled)
        
    def set_height_data_visible(self, visible: bool) -> None:
        self._set_toggle_enabled("height-data-toggle", visible)

    def set_status_visible(self, visible: bool) -> None:
        self._set_toggle_enabled("status-toggle", visible)

    def set_spc_coms_visible(self, visible: bool) -> None:
        self._set_toggle_enabled("spc-coms-toggle", visible)

    def set_keyence_coms_visible(self, visible: bool) -> None:
        self._set_toggle_enabled("keyence-coms-toggle", visible)

    def set_spc_docs_visible(self, visible: bool) -> None:
        self._set_toggle_enabled("spc-docs-toggle", visible)

    def _set_toggle_enabled(self, button_id: str, enabled: bool) -> None:
        self.query_one(f"#{button_id}", ToggleButton).set_enabled(enabled)

    def _build_control(self, config: ControlConfig) -> Button:
        if isinstance(config, ActionButtonConfig):
            return Button(
                config.label,
                id=config.button_id,
                variant=config.variant,
                classes=config.classes,
            )

        return ToggleButton(
            config.label,
            button_id=config.button_id,
            default_value=config.default_value,
            on_label=config.on_label,
            off_label=config.off_label,
            classes=config.classes,
        )

    def _control_by_id(self) -> dict[str, ControlConfig]:
        return {
            config.button_id: config
            for group in self._control_groups()
            for config in group
        }

    def _control_groups(self) -> tuple[tuple[ControlConfig, ...], ...]:
        view_toggle_classes = "control-button toggle-button view-toggle"

        return (
            (
                ActionButtonConfig(
                    "Close",
                    "close-button",
                    self.CloseRequested,
                    variant="error",
                ),
                ActionButtonConfig(
                    "Connect",
                    "connect-button",
                    self.ConnectRequested,
                    variant="primary",
                ),
            ),
            (
                ActionButtonConfig(
                    "Read",
                    "read-once-button",
                    self.ReadOnceRequested,
                ),
                ToggleButtonConfig(
                    "Keyence Stream",
                    "stream-toggle",
                    self.StreamToggleChanged,
                    on_label="Keyence Stream: ON",
                    off_label="Keyence Stream: OFF",
                    classes="control-button toggle-button stream-toggle",
                ),
            ),
            (
                ToggleButtonConfig(
                    "Height Panel",
                    "height-data-toggle",
                    self.HeightDataVisibilityChanged,
                    on_label="Height: ON",
                    off_label="Height: OFF",
                    classes=view_toggle_classes,
                ),
                ToggleButtonConfig(
                    "Status",
                    "status-toggle",
                    self.StatusVisibilityChanged,
                    default_value=True,
                    on_label="Status: ON",
                    off_label="Status: OFF",
                    classes=view_toggle_classes,
                ),
                ToggleButtonConfig(
                    "SPC Coms",
                    "spc-coms-toggle",
                    self.SpcComsVisibilityChanged,
                    default_value=True,
                    on_label="SPC: ON",
                    off_label="SPC: OFF",
                    classes=view_toggle_classes,
                ),
                ToggleButtonConfig(
                    "Keyence Coms",
                    "keyence-coms-toggle",
                    self.KeyenceComsVisibilityChanged,
                    default_value=True,
                    on_label="Keyence: ON",
                    off_label="Keyence: OFF",
                    classes=view_toggle_classes,
                ),
                ToggleButtonConfig(
                    "SPC Docs",
                    "spc-docs-toggle",
                    self.SpcDocsVisibilityChanged,
                    on_label="Docs: ON",
                    off_label="Docs: OFF",
                    classes=view_toggle_classes,
                ),
            ),
        )
    
