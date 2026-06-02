"""Plot the distribution of valid height readings."""

from __future__ import annotations

from pathlib import Path

from src.analysis.data import ExportData
from src.analysis.options import AnalysisOptions
from src.analysis.plot_helpers import metadata_title, save_figure


GRAPH_NAME = "histogram"


def create_plots(
    data: ExportData,
    output_dir: Path,
    options: AnalysisOptions,
) -> list[Path]:
    if not options.graph_enabled(GRAPH_NAME):
        return []

    import matplotlib.pyplot as plt

    valid_values = [
        sample.value_mm
        for sample in _selected_samples(data, options)
        if sample.valid
    ]

    if not valid_values:
        return []

    fig, ax = plt.subplots(figsize=(10, 6))
    bin_count = min(80, max(10, int(len(valid_values) ** 0.5)))
    ax.hist(valid_values, bins=bin_count, color="#2ca02c", edgecolor="#1b5e20", alpha=0.85)

    average = sum(valid_values) / len(valid_values)
    ax.axvline(average, color="#d62728", linewidth=1.5, label=f"Avg {average:.5f} mm")

    ax.set_title(f"Height Distribution\n{metadata_title(data, options.title)}")
    ax.set_xlabel("Height (mm)")
    ax.set_ylabel("Sample count")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best")

    if options.mark_invalid:
        invalid_count = len([
            sample
            for sample in _selected_samples(data, options)
            if not sample.valid
        ])
        ax.text(
            0.98,
            0.95,
            f"Invalid samples: {invalid_count}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "#d62728"},
            color="#d62728",
        )

    if not options.save:
        return []

    output_path = save_figure(fig, output_dir, "height_histogram.png")
    plt.close(fig)
    return [output_path]


def _selected_samples(data: ExportData, options: AnalysisOptions):
    if options.layer is None:
        return data.samples

    return data.samples_for_layer(options.layer)
