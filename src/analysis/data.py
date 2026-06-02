"""CSV loading and shared analysis data structures."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


METADATA_FIELDS = (
    "start_x",
    "start_y",
    "z",
    "scan_length",
    "scan_width",
    "delta_y",
    "scan_speed",
)


@dataclass(frozen=True)
class ExportSample:
    index: int
    source: str
    layer_index: int
    layer_sample_index: int | None
    value_mm: float
    valid: bool
    collected_at: datetime | None
    collected_at_ns: int | None
    seconds_ago: float | None


@dataclass(frozen=True)
class ExportData:
    path: Path
    source: str
    samples: list[ExportSample]
    metadata: dict[str, float | None]

    @property
    def valid_samples(self) -> list[ExportSample]:
        return [sample for sample in self.samples if sample.valid]

    @property
    def layer_indices(self) -> list[int]:
        return sorted({sample.layer_index for sample in self.samples})

    def samples_for_layer(self, layer_index: int) -> list[ExportSample]:
        return [sample for sample in self.samples if sample.layer_index == layer_index]

    def valid_samples_for_layer(self, layer_index: int) -> list[ExportSample]:
        return [
            sample
            for sample in self.samples
            if sample.layer_index == layer_index and sample.valid
        ]


def load_export_csv(path: str | Path) -> ExportData:
    csv_path = Path(path)
    samples: list[ExportSample] = []
    metadata: dict[str, float | None] = {field: None for field in METADATA_FIELDS}
    source = csv_path.stem

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            if row.get("source"):
                source = row["source"]

            for field in METADATA_FIELDS:
                value = _optional_float(row.get(field))

                if value is not None and metadata[field] is None:
                    metadata[field] = value

            samples.append(
                ExportSample(
                    index=_int(row.get("index"), default=len(samples) + 1),
                    source=row.get("source") or source,
                    layer_index=_int(row.get("layer_index"), default=0),
                    layer_sample_index=_optional_int(row.get("layer_sample_index")),
                    value_mm=_float(row.get("value_mm")),
                    valid=_bool(row.get("valid"), default=True),
                    collected_at=_optional_datetime(row.get("collected_at")),
                    collected_at_ns=_optional_int(row.get("collected_at_ns")),
                    seconds_ago=_optional_float(row.get("seconds_ago")),
                )
            )

    if not samples:
        raise ValueError(f"No rows found in export CSV: {csv_path}")

    return ExportData(path=csv_path, source=source, samples=samples, metadata=metadata)


def latest_export(export_dir: str | Path = "exports") -> Path:
    export_path = Path(export_dir)
    exports = sorted(
        export_path.glob("*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not exports:
        raise FileNotFoundError(f"No CSV exports found in {export_path.resolve()}")

    return exports[0]


def output_dir_for_export(csv_path: str | Path, root: str | Path = "analysis_outputs") -> Path:
    csv_path = Path(csv_path)
    output_dir = Path(root) / csv_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _optional_datetime(value: str | None) -> datetime | None:
    value = (value or "").strip()

    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _optional_float(value: str | None) -> float | None:
    value = (value or "").strip()

    if not value:
        return None

    return float(value)


def _float(value: str | None) -> float:
    parsed = _optional_float(value)

    if parsed is None:
        raise ValueError("Missing required float value")

    return parsed


def _optional_int(value: str | None) -> int | None:
    value = (value or "").strip()

    if not value:
        return None

    return int(value)


def _int(value: str | None, *, default: int) -> int:
    parsed = _optional_int(value)
    return default if parsed is None else parsed


def _bool(value: str | None, *, default: bool) -> bool:
    value = (value or "").strip().lower()

    if not value:
        return default

    return value in {"1", "true", "yes", "y"}
