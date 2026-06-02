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
