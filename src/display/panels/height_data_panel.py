"""Hideable split panel for height source selection and graph display."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click, Key, Resize
from textual.message import Message
from textual.widgets import Input, Label, Select, Static

from src.bridge.csv_export import CsvHeightSample, export_height_samples
from src.input.input_client import InputReading
from src.input.keyence_protocol import parse_ms3_response, parse_stream_response


CREATE_NEW_SOURCE_KEY = "__CREATE_NEW_REGISTER__"


@dataclass(frozen=True)
class GraphSample:
    value_mm: float
    valid: bool
    timestamp: float | None = None
    timestamp_ns: int | None = None
    layer_index: int = 0
    layer_sample_index: int | None = None


class HeightGraphPanel(Vertical):
    class InvalidVisibilityChanged(Message):
        def __init__(self, source: "HeightGraphPanel") -> None:
            super().__init__()
            self.source = source

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.samples: list[GraphSample] = []
        self.title = "Live Height"
        self.source_kind = "LIVE"
        self.include_invalid = True
        self.stats_override: tuple[float, float, float] | None = None
        self.total_count: int | None = None

    def compose(self) -> ComposeResult:
        self.add_class("height-graph-panel")
        with Horizontal(classes="height-title-row"):
            yield Label(self.title, id="height-graph-title", classes="panel-title")
            yield Static(
                "INV",
                id="height-include-invalid",
                classes="coms-filter-mini enabled height-invalid-toggle",
            )

        yield Static("Height: --", id="height-current-value", classes="height-current-value")
        yield Static(
            "Min: --  Max: --  Avg: --",
            id="height-graph-stats",
            classes="height-graph-stats",
        )
        yield Static("", id="height-graph")

    def on_click(self, event: Click) -> None:
        if event.widget and event.widget.id == "height-include-invalid":
            self.include_invalid = not self.include_invalid
            self._sync_invalid_toggle()
            self.post_message(self.InvalidVisibilityChanged(self))
            event.stop()

    def set_samples(
        self,
        title: str,
        samples: list[GraphSample],
        *,
        source_kind: str,
        stats: tuple[float, float, float] | None = None,
        total_count: int | None = None,
    ) -> None:
        self.title = title
        self.source_kind = source_kind
        self.samples = list(samples)
        self.stats_override = stats
        self.total_count = total_count
        self.query_one("#height-graph-title", Label).update(title)
        self._sync_invalid_toggle()
        self._render_graph()

    def set_include_invalid(self, include_invalid: bool) -> None:
        self.include_invalid = include_invalid
        self._sync_invalid_toggle()
        self._render_graph()

    def on_resize(self, _: Resize) -> None:
        self._render_graph()

    def _render_graph(self) -> None:
        graph = self.query_one("#height-graph", Static)
        value_label = self.query_one("#height-current-value", Static)
        stats_label = self.query_one("#height-graph-stats", Static)

        samples = self._display_samples()

        if not samples:
            value_label.update("Height: --")
            stats_label.update("Min: --  Max: --  Avg: --")
            graph.update("")
            return

        latest = samples[-1]

        if latest.valid:
            value_label.update(f"Height: {latest.value_mm:.5f} mm")
        else:
            value_label.update(f"Height: INVALID ({latest.value_mm:.5f} mm)")

        valid_values = [sample.value_mm for sample in samples if sample.valid]

        if self.stats_override is not None:
            min_value, max_value, avg_value = self.stats_override
            stats_label.update(
                f"Min: {min_value:.5f}  Max: {max_value:.5f}  Avg: {avg_value:.5f}"
            )
        elif valid_values:
            min_value = min(valid_values)
            max_value = max(valid_values)
            avg_value = sum(valid_values) / len(valid_values)
            stats_label.update(
                f"Min: {min_value:.5f}  Max: {max_value:.5f}  Avg: {avg_value:.5f}"
            )
        else:
            min_value = -1.0
            max_value = 1.0
            stats_label.update("Min: --  Max: --  Avg: --")

        if abs(max_value - min_value) < 1e-9:
            min_value -= 0.5
            max_value += 0.5

        rows = 8
        width = max(20, self.size.width - 9)
        visible_samples = self._samples_for_width(width)
        grid = [[" " for _ in range(width)] for _ in range(rows)]

        for x, sample in enumerate(visible_samples):
            if not sample.valid:
                for y in range(rows):
                    grid[y][x] = "x"
                continue

            normalized = (sample.value_mm - min_value) / (max_value - min_value)
            y = rows - 1 - round(normalized * (rows - 1))
            y = max(0, min(rows - 1, y))
            grid[y][x] = "-"

        lines: list[str] = []

        for row_index, row in enumerate(grid):
            if row_index == 0:
                label = f"{max_value:>7.3f} |"
            elif row_index == rows - 1:
                label = f"{min_value:>7.3f} |"
            else:
                label = "        |"

            lines.append(label + "".join(row))

        lines.append("        +" + "-" * width)
        lines.append("         " + self._axis_label(width))
        graph.update("\n".join(lines))

    def _samples_for_width(self, width: int) -> list[GraphSample]:
        samples = self._display_samples()

        if len(samples) <= width:
            return samples

        if self.source_kind == "LIVE":
            return samples[-width:]

        if width <= 1:
            return [samples[-1]]

        return [
            samples[round(index * (len(samples) - 1) / (width - 1))]
            for index in range(width)
        ]

    def _axis_label(self, width: int) -> str:
        if self.source_kind == "LIVE":
            timestamps = [
                sample.timestamp
                for sample in self._display_samples()
                if sample.timestamp is not None
            ]

            if not timestamps:
                left = "older"
            else:
                left = f"-{max(0.0, time.monotonic() - timestamps[0]):.1f}s"

            right = "now"
        else:
            left = "1"
            right = str(self.total_count or len(self._display_samples()))

        gap = max(1, width - len(left) - len(right))
        return left + (" " * gap) + right

    def _display_samples(self) -> list[GraphSample]:
        if self.include_invalid:
            return list(self.samples)

        return [sample for sample in self.samples if sample.valid]

    def _sync_invalid_toggle(self) -> None:
        toggle = self.query_one("#height-include-invalid", Static)
        toggle.set_class(self.include_invalid, "enabled")
        toggle.set_class(not self.include_invalid, "disabled")


@dataclass(frozen=True)
class HeightSource:
    key: str
    label: str
    layers: dict[int, list[float]]
    sample_count: int = 0
    min_value: float | None = None
    max_value: float | None = None
    avg_value: float | None = None
    current_layer_index: int = 0
    active: bool = False
    paused: bool = False


class HeightSourceSelector(Vertical):
    class ExportRequested(Message):
        def __init__(self, source: "HeightSourceSelector") -> None:
            super().__init__()
            self.source = source

    class CreateRegistryRequested(Message):
        def __init__(self, registry: str) -> None:
            super().__init__()
            self.registry = registry

    class ToggleRegistryRequested(Message):
        def __init__(self, source: "HeightSourceSelector") -> None:
            super().__init__()
            self.source = source

    def compose(self) -> ComposeResult:
        self.add_class("height-source-panel")
        yield Label("Height Source", classes="panel-title")
        yield Select(
            [("LIVE", "LIVE")],
            id="height-source-select",
            allow_blank=False,
            value="LIVE",
            classes="height-source-select",
        )
        yield Input(
            placeholder="New register",
            id="height-register-input",
            classes="height-register-input hidden",
            compact=True,
        )
        yield Select(
            [("ALL LAYERS", "ALL")],
            id="height-layer-select",
            allow_blank=False,
            value="ALL",
            classes="height-source-select",
        )
        with Horizontal(classes="height-layer-actions"):
            yield Static(
                "NEXT LAYER",
                id="height-next-layer",
                classes="coms-filter-mini enabled height-layer-action",
            )
            yield Static("", classes="height-action-spacer")
            yield Static(
                "START",
                id="height-toggle-register",
                classes="coms-filter-mini disabled height-register-action",
            )
            yield Static(
                "CLEAR",
                id="height-clear-register",
                classes="coms-filter-mini disabled height-register-action",
            )
        with Horizontal(classes="height-export-actions"):
            yield Static(
                "EXPORT CSV",
                id="height-export-csv",
                classes="coms-filter-mini enabled height-export-button",
            )
        yield Static("", id="height-source-list")

    def on_click(self, event: Click) -> None:
        if event.widget and event.widget.id == "height-export-csv":
            self.post_message(self.ExportRequested(self))
            event.stop()

        if event.widget and event.widget.id == "height-next-layer":
            self.post_message(self.NextLayerRequested(self))
            event.stop()

        if event.widget and event.widget.id == "height-toggle-register":
            self.post_message(self.ToggleRegistryRequested(self))
            event.stop()

        if event.widget and event.widget.id == "height-clear-register":
            self.post_message(self.ClearRegistryRequested(self))
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "height-register-input":
            return

        registry = event.input.value.strip()

        if registry:
            event.input.value = ""
            self.post_message(self.CreateRegistryRequested(registry))
        else:
            self.post_message(self.CreateRegistryRequested(""))

        event.input.blur()
        event.stop()

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            create_input = self.query_one("#height-register-input", Input)

            if create_input.has_focus:
                create_input.value = ""
                create_input.blur()
                self.post_message(self.CreateRegistryRequested(""))
                event.stop()

    class NextLayerRequested(Message):
        def __init__(self, source: "HeightSourceSelector") -> None:
            super().__init__()
            self.source = source

    class ClearRegistryRequested(Message):
        def __init__(self, source: "HeightSourceSelector") -> None:
            super().__init__()
            self.source = source


class HeightDataPanel(Horizontal):
    class ExportCompleted(Message):
        def __init__(self, path: str | None, error: str | None = None) -> None:
            super().__init__()
            self.path = path
            self.error = error

    class NextLayerRequested(Message):
        def __init__(self, registry: str | None) -> None:
            super().__init__()
            self.registry = registry

    class CreateRegistryRequested(Message):
        def __init__(self, registry: str) -> None:
            super().__init__()
            self.registry = registry

    class ToggleRegistryRequested(Message):
        def __init__(self, registry: str | None, enable: bool) -> None:
            super().__init__()
            self.registry = registry
            self.enable = enable

    class ClearRegistryRequested(Message):
        def __init__(self, registry: str | None, layer: str) -> None:
            super().__init__()
            self.registry = registry
            self.layer = layer

    def __init__(self, *args, max_live_points: int = 120, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.live_samples: deque[GraphSample] = deque(maxlen=max_live_points)
        self.sources: list[HeightSource] = []
        self.selected_source_key = "LIVE"
        self.previous_source_key = "LIVE"
        self.selected_layers: dict[str, str] = {}
        self.include_invalid = True
        self._source_select_options: tuple[tuple[str, str], ...] = ()
        self._layer_select_options: tuple[tuple[str, str], ...] = ()

    def compose(self) -> ComposeResult:
        self.add_class("panel")
        yield HeightSourceSelector(id="height-source-panel", classes="height-data-half-panel")
        yield HeightGraphPanel(id="height-graph-panel", classes="height-data-half-panel")

    def log_data(self, message: str) -> None:
        return

    def add_keyence_response(self, message: str) -> None:
        try:
            reading = self._parse_keyence_response(message)
        except ValueError:
            return

        self.live_samples.append(
            GraphSample(
                value_mm=reading.value_mm,
                valid=reading.ok,
                timestamp=time.monotonic(),
                timestamp_ns=time.time_ns(),
                layer_index=0,
            )
        )

        if self.selected_source_key == "LIVE":
            self._render_selected_source()

    def add_height(self, height_mm: float | None) -> None:
        if height_mm is None:
            return

        self.live_samples.append(
            GraphSample(
                value_mm=height_mm,
                valid=True,
                timestamp=time.monotonic(),
                timestamp_ns=time.time_ns(),
            )
        )

        if self.selected_source_key == "LIVE":
            self._render_selected_source()

    def set_tracker_sources(
        self,
        trackers: dict[
            str,
            tuple[bool, bool, int, dict[int, list[float]], int, float | None, float | None, float | None],
        ],
    ) -> None:
        self.sources = [
            HeightSource(
                key=f"TRACK:{registry}",
                label=(
                    f"{registry} "
                    f"({self._tracking_state_label(active, paused)}, "
                    f"{sample_count} samples, "
                    f"layer {current_layer})"
                ),
                layers={layer_index: list(values) for layer_index, values in layers.items()},
                sample_count=sample_count,
                min_value=min_value,
                max_value=max_value,
                avg_value=avg_value,
                current_layer_index=current_layer,
                active=active,
                paused=paused,
            )
            for registry, (
                active,
                paused,
                current_layer,
                layers,
                sample_count,
                min_value,
                max_value,
                avg_value,
            ) in sorted(trackers.items())
        ]

        available_keys = {"LIVE"} | {source.key for source in self.sources}

        if self.selected_source_key not in available_keys:
            self.selected_source_key = "LIVE"
            self.previous_source_key = "LIVE"

        self._render_source_select()
        self._render_layer_select()
        self._sync_register_action_buttons()
        self._render_source_list()
        self._render_selected_source()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id not in {"height-source-select", "height-layer-select"}:
            return

        if isinstance(event.value, str):
            if event.select.id == "height-source-select":
                if event.value == CREATE_NEW_SOURCE_KEY:
                    self._show_create_input()
                    event.stop()
                    return

                if self._create_input_is_visible() and event.value == self.selected_source_key:
                    event.stop()
                    return

                self._hide_create_input()
                self.previous_source_key = event.value
                self.selected_source_key = event.value
                self._render_layer_select()
                self._sync_register_action_buttons()
                self._render_source_list()
                self._render_selected_source()

            elif event.select.id == "height-layer-select":
                self.selected_layers[self.selected_source_key] = event.value
                self._render_source_list()
                self._render_selected_source()

        event.stop()

    def on_height_source_selector_export_requested(
        self,
        event: HeightSourceSelector.ExportRequested,
    ) -> None:
        event.stop()

        try:
            path = self.export_selected_source()
        except Exception as error:
            self.post_message(self.ExportCompleted(path=None, error=str(error)))
            return

        self.post_message(self.ExportCompleted(path=str(path)))

    def on_height_source_selector_next_layer_requested(
        self,
        event: HeightSourceSelector.NextLayerRequested,
    ) -> None:
        event.stop()
        self.post_message(self.NextLayerRequested(self._selected_registry()))

    def on_height_source_selector_toggle_registry_requested(
        self,
        event: HeightSourceSelector.ToggleRegistryRequested,
    ) -> None:
        event.stop()
        source = self._selected_tracker_source()
        self.post_message(
            self.ToggleRegistryRequested(
                self._selected_registry(),
                enable=not bool(source and source.active),
            )
        )

    def on_height_source_selector_clear_registry_requested(
        self,
        event: HeightSourceSelector.ClearRegistryRequested,
    ) -> None:
        event.stop()
        self.post_message(
            self.ClearRegistryRequested(
                self._selected_registry(),
                layer=self._selected_layer_value(),
            )
        )

    def on_height_source_selector_create_registry_requested(
        self,
        event: HeightSourceSelector.CreateRegistryRequested,
    ) -> None:
        event.stop()

        if not event.registry.strip():
            self._cancel_create_register()
            return

        self.post_message(self.CreateRegistryRequested(event.registry))

    def on_height_graph_panel_invalid_visibility_changed(
        self,
        event: HeightGraphPanel.InvalidVisibilityChanged,
    ) -> None:
        event.stop()
        self.include_invalid = event.source.include_invalid
        self._render_selected_source()

    def export_selected_source(self) -> Path:
        source_name = self._selected_export_name()
        now = time.monotonic()

        samples = [
            CsvHeightSample(
                value_mm=sample.value_mm,
                valid=sample.valid,
                seconds_ago=(
                    None
                    if sample.timestamp is None
                    else max(0.0, now - sample.timestamp)
                ),
                layer_index=sample.layer_index,
                layer_sample_index=sample.layer_sample_index,
                collected_at_ns=sample.timestamp_ns,
            )
            for sample in self._selected_samples()
        ]

        return export_height_samples(source_name=source_name, samples=samples)

    def _render_source_list(self) -> None:
        layer_label = self._selected_layer_label()
        rows = [
            self._source_row(
                key="LIVE",
                label=f"LIVE ({len(self.live_samples)} samples)",
                active=True,
            )
        ]

        for source in self.sources:
            rows.append(
                self._source_row(
                    key=source.key,
                    label=(
                        f"{source.label}"
                        f"{' [view: ' + layer_label + ']' if source.key == self.selected_source_key else ''}"
                    ),
                    active=source.active,
                )
            )

        self.query_one("#height-source-list", Static).update("\n".join(rows))

    def _render_source_select(self) -> None:
        select = self.query_one("#height-source-select", Select)
        options = tuple([("LIVE", "LIVE")] + [
            (source.label, source.key)
            for source in self.sources
        ] + [("CREATE NEW...", CREATE_NEW_SOURCE_KEY)])

        if options != self._source_select_options:
            select.set_options(list(options))
            self._source_select_options = options

        if select.value != self.selected_source_key:
            select.value = self.selected_source_key

    def _render_layer_select(self) -> None:
        select = self.query_one("#height-layer-select", Select)
        source = self._selected_tracker_source()

        if source is None:
            options = (("ALL LAYERS", "ALL"),)

            if options != self._layer_select_options:
                select.set_options(list(options))
                self._layer_select_options = options

            if select.value != "ALL":
                select.value = "ALL"

            return

        options = tuple([("ALL LAYERS", "ALL")] + [
            (f"LAYER {layer_index}", str(layer_index))
            for layer_index in sorted(source.layers.keys())
        ])

        selected = self.selected_layers.get(source.key, "ALL")
        available_values = {value for _, value in options}

        if selected not in available_values:
            selected = "ALL"

        if options != self._layer_select_options:
            select.set_options(list(options))
            self._layer_select_options = options

        if select.value != selected:
            select.value = selected

    def _sync_register_action_buttons(self) -> None:
        source = self._selected_tracker_source()
        is_registry = source is not None
        is_active = bool(source and source.active)

        toggle = self.query_one("#height-toggle-register", Static)
        toggle.update("STOP" if is_active else "START")
        self._set_action_enabled("#height-toggle-register", is_registry)
        self._set_action_enabled("#height-clear-register", is_registry)

    def _set_action_enabled(self, selector: str, enabled: bool) -> None:
        button = self.query_one(selector, Static)
        button.set_class(enabled, "enabled")
        button.set_class(not enabled, "disabled")

    def _source_row(self, key: str, label: str, active: bool) -> str:
        selected = ">" if key == self.selected_source_key else " "
        state = "*" if active else " "
        return f"{selected} {state} {label}"

    def _render_selected_source(self) -> None:
        graph = self.query_one("#height-graph-panel", HeightGraphPanel)
        graph.set_include_invalid(self.include_invalid)

        if self.selected_source_key == "LIVE":
            graph.set_samples(
                "Live Height",
                list(self.live_samples),
                source_kind="LIVE",
            )
            return

        source = self._selected_tracker_source()

        if source is None:
            graph.set_samples(
                "Live Height",
                list(self.live_samples),
                source_kind="LIVE",
            )
            return

        graph.set_samples(
            f"Tracking {source.key.removeprefix('TRACK:')} ({self._selected_layer_label()})",
            self._selected_tracker_graph_samples(source),
            source_kind="TRACK",
            stats=self._selected_tracker_stats(source),
            total_count=self._selected_tracker_count(source),
        )

    def _selected_samples(self) -> list[GraphSample]:
        if self.selected_source_key == "LIVE":
            samples = list(self.live_samples)
            return self._filter_invalid_samples(samples)

        source = self._selected_tracker_source()

        if source is None:
            return []

        return self._filter_invalid_samples(self._selected_tracker_samples(source))

    def _selected_export_name(self) -> str:
        if self.selected_source_key == "LIVE":
            return "live"

        return f"register-{self.selected_source_key.removeprefix('TRACK:')}"

    def _selected_registry(self) -> str | None:
        if not self.selected_source_key.startswith("TRACK:"):
            return None

        return self.selected_source_key.removeprefix("TRACK:")

    def select_registry(self, registry: str) -> None:
        self.selected_source_key = f"TRACK:{registry}"
        self.previous_source_key = self.selected_source_key
        self.selected_layers.setdefault(self.selected_source_key, "ALL")
        self._hide_create_input()
        self._render_source_select()
        self._render_layer_select()
        self._sync_register_action_buttons()
        self._render_source_list()
        self._render_selected_source()

    def _show_create_input(self) -> None:
        self.selected_source_key = self.previous_source_key
        self._render_source_select()
        create_input = self.query_one("#height-register-input", Input)
        create_input.remove_class("hidden")
        create_input.value = ""
        create_input.focus()

    def _hide_create_input(self) -> None:
        create_input = self.query_one("#height-register-input", Input)
        create_input.add_class("hidden")
        create_input.value = ""
        create_input.blur()

    def _create_input_is_visible(self) -> bool:
        return not self.query_one("#height-register-input", Input).has_class("hidden")

    def _cancel_create_register(self) -> None:
        self.selected_source_key = self.previous_source_key
        self._hide_create_input()
        self._render_source_select()
        self._render_layer_select()
        self._sync_register_action_buttons()
        self._render_source_list()
        self._render_selected_source()

    def _selected_tracker_source(self) -> HeightSource | None:
        return next(
            (
                source
                for source in self.sources
                if source.key == self.selected_source_key
            ),
            None,
        )

    def _selected_tracker_samples(self, source: HeightSource) -> list[GraphSample]:
        selected_layer = self.selected_layers.get(source.key, "ALL")

        if selected_layer == "ALL":
            return self._tracker_samples_from_layers(source.layers)

        try:
            layer_index = int(selected_layer)
        except ValueError:
            return self._tracker_samples_from_layers(source.layers)

        return [
            GraphSample(
                value_mm=value,
                valid=True,
                layer_index=layer_index,
                layer_sample_index=sample_index,
            )
            for sample_index, value in enumerate(source.layers.get(layer_index, []), start=1)
        ]

    def _selected_tracker_graph_samples(self, source: HeightSource) -> list[GraphSample]:
        total_count = self._selected_tracker_count(source)

        if total_count == 0:
            return []

        graph = self.query_one("#height-graph-panel", HeightGraphPanel)
        width = max(20, graph.size.width - 9)

        if total_count <= width:
            return self._selected_tracker_samples(source)

        if width <= 1:
            point = self._selected_tracker_point_at(source, total_count - 1)
            return [] if point is None else [point]

        return [
            point
            for index in range(width)
            if (point := self._selected_tracker_point_at(
                source,
                round(index * (total_count - 1) / (width - 1)),
            ))
            is not None
        ]

    def _selected_tracker_point_at(
        self,
        source: HeightSource,
        flat_index: int,
    ) -> GraphSample | None:
        selected_layer = self.selected_layers.get(source.key, "ALL")

        if selected_layer != "ALL":
            try:
                layer_index = int(selected_layer)
            except ValueError:
                selected_layer = "ALL"
            else:
                values = source.layers.get(layer_index, [])

                if not 0 <= flat_index < len(values):
                    return None

                return GraphSample(
                    value_mm=values[flat_index],
                    valid=True,
                    layer_index=layer_index,
                    layer_sample_index=flat_index + 1,
                )

        offset = flat_index

        for layer_index, values in sorted(source.layers.items()):
            if offset < len(values):
                return GraphSample(
                    value_mm=values[offset],
                    valid=True,
                    layer_index=layer_index,
                    layer_sample_index=offset + 1,
                )

            offset -= len(values)

        return None

    def _selected_tracker_count(self, source: HeightSource) -> int:
        selected_layer = self.selected_layers.get(source.key, "ALL")

        if selected_layer == "ALL":
            return source.sample_count

        try:
            layer_index = int(selected_layer)
        except ValueError:
            return self._layer_count(source.layers)

        return len(source.layers.get(layer_index, []))

    def _selected_tracker_stats(self, source: HeightSource) -> tuple[float, float, float] | None:
        selected_layer = self.selected_layers.get(source.key, "ALL")

        if selected_layer == "ALL":
            if (
                source.sample_count == 0
                or source.min_value is None
                or source.max_value is None
                or source.avg_value is None
            ):
                return None

            return source.min_value, source.max_value, source.avg_value

        values = self._selected_tracker_values(source)

        if not values:
            return None

        return min(values), max(values), sum(values) / len(values)

    def _selected_tracker_values(self, source: HeightSource) -> list[float]:
        selected_layer = self.selected_layers.get(source.key, "ALL")

        if selected_layer == "ALL":
            return [
                value
                for _, values in sorted(source.layers.items())
                for value in values
            ]

        try:
            layer_index = int(selected_layer)
        except ValueError:
            return [
                value
                for _, values in sorted(source.layers.items())
                for value in values
            ]

        return list(source.layers.get(layer_index, []))

    @staticmethod
    def _tracker_samples_from_layers(
        layers: dict[int, list[float]],
    ) -> list[GraphSample]:
        return [
            GraphSample(
                value_mm=value,
                valid=True,
                layer_index=layer_index,
                layer_sample_index=sample_index,
            )
            for layer_index, values in sorted(layers.items())
            for sample_index, value in enumerate(values, start=1)
        ]

    def _selected_layer_label(self) -> str:
        source = self._selected_tracker_source()

        if source is None:
            return "ALL"

        selected_layer = self._selected_layer_value()
        return "ALL" if selected_layer == "ALL" else f"LAYER {selected_layer}"

    def _selected_layer_value(self) -> str:
        source = self._selected_tracker_source()

        if source is None:
            return "ALL"

        return self.selected_layers.get(source.key, "ALL")

    def _filter_invalid_samples(self, samples: list[GraphSample]) -> list[GraphSample]:
        if self.include_invalid:
            return samples

        return [sample for sample in samples if sample.valid]

    @staticmethod
    def _layer_count(layers: dict[int, list[float]]) -> int:
        return sum(len(values) for values in layers.values())

    @staticmethod
    def _tracking_state_label(active: bool, paused: bool) -> str:
        if active and paused:
            return "PAUSED"

        return "ON" if active else "OFF"

    @staticmethod
    def _parse_keyence_response(message: str) -> InputReading:
        message = message.strip()

        if message.startswith("MS,"):
            return parse_ms3_response(message)

        return parse_stream_response(message)
