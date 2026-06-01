"""Named height tracking buffers.

SPC can start independent tracking registries, then later request the raw
samples or summary values from each registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
import time


@dataclass(frozen=True)
class ScanMetadata:
    start_x: float | None = None
    start_y: float | None = None
    scan_length: float | None = None
    scan_width: float | None = None
    delta_y: float | None = None
    scan_speed: float | None = None


@dataclass(frozen=True)
class TrackedHeightSample:
    value_mm: float
    layer_index: int
    layer_sample_index: int
    collected_at_ns: int

    @property
    def collected_at(self) -> datetime:
        return datetime.fromtimestamp(self.collected_at_ns / 1_000_000_000)


@dataclass
class HeightTrack:
    active: bool = False
    paused: bool = False
    current_layer_index: int = 0
    samples: list[TrackedHeightSample] = field(default_factory=list)
    layers: dict[int, list[TrackedHeightSample]] = field(default_factory=dict)
    sum_value: float = 0.0
    min_value: float | None = None
    max_value: float | None = None
    metadata: ScanMetadata = field(default_factory=ScanMetadata)
    dirty: bool = False


class HeightTrackerManager:
    def __init__(self) -> None:
        self._tracks: dict[str, HeightTrack] = {}
        self._lock = RLock()

    def ensure(self, registry: str) -> str:
        with self._lock:
            registry = normalize_registry_name(registry)
            self._get_track(registry)
            return registry

    def start(self, registry: str) -> None:
        with self._lock:
            track = self._get_track(registry)
            track.active = True
            track.paused = False

    def stop(self, registry: str) -> None:
        with self._lock:
            track = self._get_track(registry)
            track.active = False
            track.paused = False

    def pause(self, registry: str) -> None:
        with self._lock:
            self._get_track(registry).paused = True

    def resume(self, registry: str) -> None:
        with self._lock:
            track = self._get_track(registry)
            track.active = True
            track.paused = False

    def clear(self, registry: str) -> None:
        with self._lock:
            track = self._get_track(registry)
            track.samples.clear()
            track.layers.clear()
            track.current_layer_index = 0
            track.sum_value = 0.0
            track.min_value = None
            track.max_value = None
            track.dirty = False

    def clear_layer(self, registry: str, layer_index: int) -> None:
        with self._lock:
            track = self._get_track(registry)
            removed_samples = track.layers.pop(layer_index, [])

            if not removed_samples:
                return

            removed_ids = {id(sample) for sample in removed_samples}
            track.samples = [
                sample for sample in track.samples if id(sample) not in removed_ids
            ]
            self._recalculate_summary(track)
            track.dirty = bool(track.samples)

    def next_layer(self, registry: str) -> int:
        with self._lock:
            track = self._get_track(registry)
            track.current_layer_index += 1
            return track.current_layer_index

    def add_sample(self, value_mm: float) -> None:
        collected_at_ns = time.time_ns()

        with self._lock:
            for track in self._tracks.values():
                if track.active and not track.paused:
                    layer_samples = track.layers.setdefault(track.current_layer_index, [])
                    sample = TrackedHeightSample(
                        value_mm=value_mm,
                        layer_index=track.current_layer_index,
                        layer_sample_index=len(layer_samples) + 1,
                        collected_at_ns=collected_at_ns,
                    )
                    layer_samples.append(sample)
                    track.samples.append(sample)
                    track.dirty = True
                    self._record_summary(track, value_mm)

    def set_metadata(
        self,
        registry: str,
        *,
        start_x: float | None = None,
        start_y: float | None = None,
        scan_length: float | None = None,
        scan_width: float | None = None,
        delta_y: float | None = None,
        scan_speed: float | None = None,
    ) -> ScanMetadata:
        with self._lock:
            track = self._get_track(registry)
            current = track.metadata
            track.metadata = ScanMetadata(
                start_x=current.start_x if start_x is None else start_x,
                start_y=current.start_y if start_y is None else start_y,
                scan_length=current.scan_length if scan_length is None else scan_length,
                scan_width=current.scan_width if scan_width is None else scan_width,
                delta_y=current.delta_y if delta_y is None else delta_y,
                scan_speed=current.scan_speed if scan_speed is None else scan_speed,
            )
            track.dirty = bool(track.samples)
            return track.metadata

    def metadata(self, registry: str) -> ScanMetadata:
        with self._lock:
            return self._get_track(registry).metadata

    def values(self, registry: str) -> list[float]:
        return [sample.value_mm for sample in self.samples(registry)]

    def samples(self, registry: str) -> list[TrackedHeightSample]:
        with self._lock:
            return list(self._get_track(registry).samples)

    def layers(self, registry: str) -> dict[int, list[float]]:
        with self._lock:
            return {
                layer_index: [sample.value_mm for sample in samples]
                for layer_index, samples in self._get_track(registry).layers.items()
            }

    def registries(self) -> list[str]:
        with self._lock:
            return sorted(self._tracks.keys())

    def dirty_registries(self) -> list[str]:
        with self._lock:
            return sorted(
                registry
                for registry, track in self._tracks.items()
                if track.dirty and track.samples
            )

    def mark_exported(self, registry: str) -> None:
        with self._lock:
            self._get_track(registry).dirty = False

    def average(self, registry: str) -> float | None:
        with self._lock:
            track = self._get_track(registry)
            return track.sum_value / len(track.samples) if track.samples else None

    def minimum(self, registry: str) -> float | None:
        with self._lock:
            return self._get_track(registry).min_value

    def maximum(self, registry: str) -> float | None:
        with self._lock:
            return self._get_track(registry).max_value

    def count(self, registry: str) -> int:
        with self._lock:
            return len(self._get_track(registry).samples)

    def is_active(self, registry: str) -> bool:
        with self._lock:
            return self._get_track(registry).active

    def is_paused(self, registry: str) -> bool:
        with self._lock:
            return self._get_track(registry).paused

    def current_layer(self, registry: str) -> int:
        with self._lock:
            return self._get_track(registry).current_layer_index

    def _get_track(self, registry: str) -> HeightTrack:
        registry = normalize_registry_name(registry)
        track = self._tracks.get(registry)

        if track is None:
            track = HeightTrack()
            self._tracks[registry] = track

        return track

    @staticmethod
    def _record_summary(track: HeightTrack, value_mm: float) -> None:
        track.sum_value += value_mm
        track.min_value = (
            value_mm if track.min_value is None else min(track.min_value, value_mm)
        )
        track.max_value = (
            value_mm if track.max_value is None else max(track.max_value, value_mm)
        )

    @staticmethod
    def _recalculate_summary(track: HeightTrack) -> None:
        track.sum_value = sum(sample.value_mm for sample in track.samples)

        if not track.samples:
            track.min_value = None
            track.max_value = None
            return

        values = [sample.value_mm for sample in track.samples]
        track.min_value = min(values)
        track.max_value = max(values)


def normalize_registry_name(registry: str) -> str:
    registry = registry.strip().upper()

    if not registry:
        raise ValueError("Tracking registry name is required")

    return registry
