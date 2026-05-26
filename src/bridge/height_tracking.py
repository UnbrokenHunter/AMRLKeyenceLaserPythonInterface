"""Named height tracking buffers.

SPC can start independent tracking registries, then later request the raw
samples or summary values from each registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean


@dataclass(frozen=True)
class TrackedHeightSample:
    value_mm: float
    layer_index: int
    layer_sample_index: int


@dataclass
class HeightTrack:
    active: bool = False
    current_layer_index: int = 0
    samples: list[TrackedHeightSample] = field(default_factory=list)


class HeightTrackerManager:
    def __init__(self) -> None:
        self._tracks: dict[str, HeightTrack] = {}

    def start(self, registry: str) -> None:
        self._get_track(registry).active = True

    def stop(self, registry: str) -> None:
        self._get_track(registry).active = False

    def clear(self, registry: str) -> None:
        track = self._get_track(registry)
        track.samples.clear()
        track.current_layer_index = 0

    def next_layer(self, registry: str) -> int:
        track = self._get_track(registry)
        track.current_layer_index += 1
        return track.current_layer_index

    def add_sample(self, value_mm: float) -> None:
        for track in self._tracks.values():
            if track.active:
                layer_sample_index = (
                    sum(
                        1
                        for sample in track.samples
                        if sample.layer_index == track.current_layer_index
                    )
                    + 1
                )
                track.samples.append(
                    TrackedHeightSample(
                        value_mm=value_mm,
                        layer_index=track.current_layer_index,
                        layer_sample_index=layer_sample_index,
                    )
                )

    def values(self, registry: str) -> list[float]:
        return [sample.value_mm for sample in self.samples(registry)]

    def samples(self, registry: str) -> list[TrackedHeightSample]:
        return list(self._get_track(registry).samples)

    def layers(self, registry: str) -> dict[int, list[float]]:
        layers: dict[int, list[float]] = {}

        for sample in self.samples(registry):
            layers.setdefault(sample.layer_index, []).append(sample.value_mm)

        return layers

    def registries(self) -> list[str]:
        return sorted(self._tracks.keys())

    def average(self, registry: str) -> float | None:
        samples = self.values(registry)
        return mean(samples) if samples else None

    def minimum(self, registry: str) -> float | None:
        samples = self.values(registry)
        return min(samples) if samples else None

    def maximum(self, registry: str) -> float | None:
        samples = self.values(registry)
        return max(samples) if samples else None

    def count(self, registry: str) -> int:
        return len(self._get_track(registry).samples)

    def is_active(self, registry: str) -> bool:
        return self._get_track(registry).active

    def current_layer(self, registry: str) -> int:
        return self._get_track(registry).current_layer_index

    def _get_track(self, registry: str) -> HeightTrack:
        registry = normalize_registry_name(registry)
        track = self._tracks.get(registry)

        if track is None:
            track = HeightTrack()
            self._tracks[registry] = track

        return track


def normalize_registry_name(registry: str) -> str:
    registry = registry.strip().upper()

    if not registry:
        raise ValueError("Tracking registry name is required")

    return registry
