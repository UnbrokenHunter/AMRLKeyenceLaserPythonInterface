"""Named height tracking buffers.

SPC can start independent tracking registries, then later request the raw
samples or summary values from each registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrackedHeightSample:
    value_mm: float
    layer_index: int
    layer_sample_index: int


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


class HeightTrackerManager:
    def __init__(self) -> None:
        self._tracks: dict[str, HeightTrack] = {}

    def ensure(self, registry: str) -> str:
        registry = normalize_registry_name(registry)
        self._get_track(registry)
        return registry

    def start(self, registry: str) -> None:
        track = self._get_track(registry)
        track.active = True
        track.paused = False

    def stop(self, registry: str) -> None:
        track = self._get_track(registry)
        track.active = False
        track.paused = False

    def pause(self, registry: str) -> None:
        self._get_track(registry).paused = True

    def resume(self, registry: str) -> None:
        track = self._get_track(registry)
        track.active = True
        track.paused = False

    def clear(self, registry: str) -> None:
        track = self._get_track(registry)
        track.samples.clear()
        track.layers.clear()
        track.current_layer_index = 0
        track.sum_value = 0.0
        track.min_value = None
        track.max_value = None

    def clear_layer(self, registry: str, layer_index: int) -> None:
        track = self._get_track(registry)
        removed_samples = track.layers.pop(layer_index, [])

        if not removed_samples:
            return

        removed_ids = {id(sample) for sample in removed_samples}
        track.samples = [
            sample for sample in track.samples if id(sample) not in removed_ids
        ]
        self._recalculate_summary(track)

    def next_layer(self, registry: str) -> int:
        track = self._get_track(registry)
        track.current_layer_index += 1
        return track.current_layer_index

    def add_sample(self, value_mm: float) -> None:
        for track in self._tracks.values():
            if track.active and not track.paused:
                layer_samples = track.layers.setdefault(track.current_layer_index, [])
                sample = TrackedHeightSample(
                    value_mm=value_mm,
                    layer_index=track.current_layer_index,
                    layer_sample_index=len(layer_samples) + 1,
                )
                layer_samples.append(sample)
                track.samples.append(sample)
                self._record_summary(track, value_mm)

    def values(self, registry: str) -> list[float]:
        return [sample.value_mm for sample in self.samples(registry)]

    def samples(self, registry: str) -> list[TrackedHeightSample]:
        return list(self._get_track(registry).samples)

    def layers(self, registry: str) -> dict[int, list[float]]:
        return {
            layer_index: [sample.value_mm for sample in samples]
            for layer_index, samples in self._get_track(registry).layers.items()
        }

    def registries(self) -> list[str]:
        return sorted(self._tracks.keys())

    def average(self, registry: str) -> float | None:
        track = self._get_track(registry)
        return track.sum_value / len(track.samples) if track.samples else None

    def minimum(self, registry: str) -> float | None:
        return self._get_track(registry).min_value

    def maximum(self, registry: str) -> float | None:
        return self._get_track(registry).max_value

    def count(self, registry: str) -> int:
        return len(self._get_track(registry).samples)

    def is_active(self, registry: str) -> bool:
        return self._get_track(registry).active

    def is_paused(self, registry: str) -> bool:
        return self._get_track(registry).paused

    def current_layer(self, registry: str) -> int:
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
