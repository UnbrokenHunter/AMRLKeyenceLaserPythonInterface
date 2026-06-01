"""CSV export helpers for height samples."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Iterable


@dataclass(frozen=True)
class CsvHeightSample:
    value_mm: float
    valid: bool = True
    seconds_ago: float | None = None
    layer_index: int = 0
    layer_sample_index: int | None = None
    collected_at: datetime | None = None
    collected_at_ns: int | None = None
    start_x: float | None = None
    start_y: float | None = None
    scan_length: float | None = None
    scan_width: float | None = None
    delta_y: float | None = None
    scan_speed: float | None = None


def export_height_samples(
    *,
    source_name: str,
    samples: Iterable[CsvHeightSample],
    export_dir: str | Path = "exports",
    keep_count: int = 25,
) -> Path:
    sample_list = list(samples)

    if not sample_list:
        raise ValueError(f"No samples to export for {source_name}")

    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)

    file_path = export_path / _export_filename(source_name)

    with file_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "index",
                "source",
                "layer_index",
                "layer_sample_index",
                "collected_at",
                "collected_at_ns",
                "value_mm",
                "valid",
                "seconds_ago",
                "start_x",
                "start_y",
                "scan_length",
                "scan_width",
                "delta_y",
                "scan_speed",
            ]
        )

        for index, sample in enumerate(sample_list, start=1):
            collected_at = sample.collected_at

            if collected_at is None and sample.collected_at_ns is not None:
                collected_at = datetime.fromtimestamp(
                    sample.collected_at_ns / 1_000_000_000
                )

            writer.writerow(
                [
                    index,
                    source_name,
                    sample.layer_index,
                    "" if sample.layer_sample_index is None else sample.layer_sample_index,
                    (
                        ""
                        if collected_at is None
                        else collected_at.isoformat(timespec="microseconds")
                    ),
                    "" if sample.collected_at_ns is None else sample.collected_at_ns,
                    f"{sample.value_mm:.5f}",
                    int(sample.valid),
                    "" if sample.seconds_ago is None else f"{sample.seconds_ago:.3f}",
                    _format_optional_float(sample.start_x),
                    _format_optional_float(sample.start_y),
                    _format_optional_float(sample.scan_length),
                    _format_optional_float(sample.scan_width),
                    _format_optional_float(sample.delta_y),
                    _format_optional_float(sample.scan_speed),
                ]
            )

    prune_exports(export_path, keep_count=keep_count)
    return file_path


def prune_exports(export_dir: str | Path = "exports", *, keep_count: int = 25) -> None:
    keep_count = max(0, int(keep_count))

    if keep_count == 0:
        return

    export_path = Path(export_dir)

    if not export_path.exists():
        return

    exports = sorted(
        export_path.glob("*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for old_export in exports[keep_count:]:
        try:
            old_export.unlink()
        except OSError:
            pass


def _export_filename(source_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_source = re.sub(r"[^A-Za-z0-9_-]+", "-", source_name.strip()).strip("-")

    if not safe_source:
        safe_source = "height"

    return f"{safe_source}-{timestamp}.csv"


def _format_optional_float(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"
