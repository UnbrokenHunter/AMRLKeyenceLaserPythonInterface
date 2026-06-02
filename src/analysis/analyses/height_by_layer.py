"""Plot height traces grouped by scan layer."""

from __future__ import annotations

from pathlib import Path

from src.analysis.data import ExportData
from src.analysis.options import AnalysisOptions
from src.analysis.plot_helpers import metadata_title, sample_axis, save_figure


GRAPH_NAME = "layers"


def create_plots(
    data: ExportData,
    output_dir: Path,
    options: AnalysisOptions,
) -> list[Path]:
    if not options.graph_enabled(GRAPH_NAME):
        return []

    import matplotlib.pyplot as plt

    layer_indices = [options.layer] if options.layer is not None else data.layer_indices

    if not layer_indices:
        return []

    fig, ax = plt.subplots(figsize=(12, 6))

    for layer_index in layer_indices:
        samples = data.samples_for_layer(layer_index)

        if not samples:
            continue

        x_values, _ = sample_axis(samples)
        y_values = [sample.value_mm for sample in samples]
        ax.plot(x_values, y_values, linewidth=1.0, label=f"Layer {layer_index}")

        if options.mark_invalid:
            invalid_x = [
                x for x, sample in zip(x_values, samples) if not sample.valid
            ]
            invalid_y = [sample.value_mm for sample in samples if not sample.valid]

            if invalid_x:
                ax.scatter(
                    invalid_x,
                    invalid_y,
                    color="#d62728",
                    marker="x",
                    s=22,
                    label=f"Layer {layer_index} invalid",
                    zorder=3,
                )

    title = "Height Layer" if options.layer is not None else "Height By Layer"
    ax.set_title(f"{title}\n{metadata_title(data, options.title)}")
    ax.set_xlabel("Layer sample time/index")
    ax.set_ylabel("Height (mm)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")

    if not options.save:
        return []

    output_path = save_figure(fig, output_dir, "height_by_layer.png")
    plt.close(fig)
    return [output_path]
