"""Write a plain-text summary beside the generated plots."""

from __future__ import annotations

from pathlib import Path

from src.analysis.data import ExportData
from src.analysis.options import AnalysisOptions


GRAPH_NAME = "summary"


def create_plots(
    data: ExportData,
    output_dir: Path,
    options: AnalysisOptions,
) -> list[Path]:
    if not options.graph_enabled(GRAPH_NAME):
        return []

    samples = _selected_samples(data, options)
    valid_values = [sample.value_mm for sample in samples if sample.valid]
    lines = [
        f"Title: {options.title or data.source}",
        f"Source: {data.source}",
        f"CSV: {data.path}",
        f"Layer filter: {options.layer if options.layer is not None else 'ALL'}",
        f"Height filter: {_height_filter_label(options)}",
        f"Original samples: {options.original_sample_count if options.original_sample_count is not None else len(samples)}",
        f"Filtered samples: {options.filtered_sample_count}",
        f"Dropped samples: {options.dropped_sample_count}",
        f"Total samples: {len(samples)}",
        f"Valid samples: {len(valid_values)}",
        f"Invalid samples: {len(samples) - len(valid_values)}",
        f"Layers: {', '.join(str(layer) for layer in data.layer_indices)}",
        "",
        "Metadata:",
    ]

    for field, value in data.metadata.items():
        lines.append(f"  {field}: {'' if value is None else value}")

    if valid_values:
        average = sum(valid_values) / len(valid_values)
        lines.extend(
            [
                "",
                "Valid height stats:",
                f"  min_mm: {min(valid_values):.6f}",
                f"  max_mm: {max(valid_values):.6f}",
                f"  avg_mm: {average:.6f}",
            ]
        )

    if not options.save:
        print("")
        print("\n".join(lines))
        return []

    output_path = output_dir / "summary.txt"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [output_path]


def _selected_samples(data: ExportData, options: AnalysisOptions):
    if options.layer is None:
        return data.samples

    return data.samples_for_layer(options.layer)


def _height_filter_label(options: AnalysisOptions) -> str:
    if options.min_height is None and options.max_height is None:
        return "OFF"

    bounds = []

    if options.min_height is not None:
        bounds.append(f"min={options.min_height:g}")

    if options.max_height is not None:
        bounds.append(f"max={options.max_height:g}")

    mode = "drop" if options.drop_filtered else "mark invalid"
    return f"{', '.join(bounds)} ({mode})"
