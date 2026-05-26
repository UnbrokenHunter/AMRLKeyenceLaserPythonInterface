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


def export_height_samples(
    *,
    source_name: str,
    samples: Iterable[CsvHeightSample],
    export_dir: str | Path = "exports",
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
                "value_mm",
                "valid",
                "seconds_ago",
            ]
        )

        for index, sample in enumerate(sample_list, start=1):
            writer.writerow(
                [
                    index,
                    source_name,
                    sample.layer_index,
                    "" if sample.layer_sample_index is None else sample.layer_sample_index,
                    f"{sample.value_mm:.5f}",
                    int(sample.valid),
                    "" if sample.seconds_ago is None else f"{sample.seconds_ago:.3f}",
                ]
            )

    return file_path


def _export_filename(source_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_source = re.sub(r"[^A-Za-z0-9_-]+", "-", source_name.strip()).strip("-")

    if not safe_source:
        safe_source = "height"

    return f"{safe_source}-{timestamp}.csv"
