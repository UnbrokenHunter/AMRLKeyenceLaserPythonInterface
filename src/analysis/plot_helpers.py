"""Shared Matplotlib helpers for export analyses."""

from __future__ import annotations

from pathlib import Path

from src.analysis.data import ExportData, ExportSample


def configure_matplotlib() -> None:
    import matplotlib.pyplot  # noqa: F401


def sample_axis(samples: list[ExportSample]) -> tuple[list[float], str]:
    ns_values = [sample.collected_at_ns for sample in samples]

    if ns_values and all(value is not None for value in ns_values):
        start_ns = int(ns_values[0])
        return [
            (int(sample.collected_at_ns) - start_ns) / 1_000_000_000
            for sample in samples
        ], "Time since first sample (s)"

    metadata_indices = [
        sample.layer_sample_index
        for sample in samples
        if sample.layer_sample_index is not None
    ]

    if metadata_indices and len(metadata_indices) == len(samples):
        return [float(index) for index in metadata_indices], "Layer sample index"

    return [float(sample.index) for sample in samples], "Sample index"


def metadata_title(data: ExportData, title: str | None = None) -> str:
    metadata_parts = []

    for label, field, unit in (
        ("X", "start_x", ""),
        ("Y", "start_y", ""),
        ("Length", "scan_length", ""),
        ("Width", "scan_width", ""),
        ("dY", "delta_y", ""),
        ("Speed", "scan_speed", ""),
    ):
        value = data.metadata.get(field)

        if value is not None:
            metadata_parts.append(f"{label}={value:g}{unit}")

    base_title = title or data.source

    if not metadata_parts:
        return base_title

    return f"{base_title}\n" + "  ".join(metadata_parts)


def save_figure(fig, output_dir: Path, filename: str) -> Path:
    output_path = output_dir / filename
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    return output_path
