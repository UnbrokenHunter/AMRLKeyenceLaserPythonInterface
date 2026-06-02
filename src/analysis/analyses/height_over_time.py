"""Plot height values against timestamp or sample index."""

from __future__ import annotations

from pathlib import Path

from src.analysis.data import ExportData
from src.analysis.options import AnalysisOptions
from src.analysis.plot_helpers import metadata_title, sample_axis, save_figure


GRAPH_NAME = "trace"


def create_plots(
    data: ExportData,
    output_dir: Path,
    options: AnalysisOptions,
) -> list[Path]:
    if not options.graph_enabled(GRAPH_NAME):
        return []

    import matplotlib.pyplot as plt

    samples = _selected_samples(data, options)

    if not samples:
        return []

    x_values, x_label = sample_axis(samples)
    y_values = [sample.value_mm for sample in samples]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(x_values, y_values, linewidth=1.0, color="#1f77b4")

    invalid_x = [
        x
        for x, sample in zip(x_values, samples)
        if options.mark_invalid and not sample.valid
    ]
    invalid_y = [
        sample.value_mm
        for sample in samples
        if options.mark_invalid and not sample.valid
    ]

    if invalid_x:
        ax.scatter(
            invalid_x,
            invalid_y,
            color="#d62728",
            s=18,
            label="Invalid",
            zorder=3,
        )
        ax.legend(loc="best")

    ax.set_title(f"Height Trace\n{metadata_title(data, options.title)}")
    ax.set_xlabel(x_label)
    ax.set_ylabel("Height (mm)")
    ax.grid(True, alpha=0.3)

    if not options.save:
        return []

    output_path = save_figure(fig, output_dir, "height_trace.png")
    plt.close(fig)
    return [output_path]


def _selected_samples(data: ExportData, options: AnalysisOptions):
    if options.layer is None:
        return data.samples

    return data.samples_for_layer(options.layer)
