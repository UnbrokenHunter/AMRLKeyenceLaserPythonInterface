"""Named height tracking buffers.

SPC can start independent tracking registries, then later request the raw
samples or summary values from each registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean


@dataclass
class HeightTrack:
    active: bool = False
    samples: list[float] = field(default_factory=list)


class HeightTrackerManager:
    def __init__(self) -> None:
        self._tracks: dict[str, HeightTrack] = {}

    def start(self, registry: str) -> None:
        self._get_track(registry).active = True

    def stop(self, registry: str) -> None:
        self._get_track(registry).active = False

    def clear(self, registry: str) -> None:
        self._get_track(registry).samples.clear()

    def add_sample(self, value_mm: float) -> None:
        for track in self._tracks.values():
            if track.active:
                track.samples.append(value_mm)

    def values(self, registry: str) -> list[float]:
        return list(self._get_track(registry).samples)

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
