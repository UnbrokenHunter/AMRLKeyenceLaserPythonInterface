"""Run all export analyses on the newest CSV export.

This module is intentionally independent from the bridge UI and serial runtime.
It only reads CSV files from the exports folder and writes derived analysis files
to analysis_outputs.
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
from pathlib import Path

from src.analysis import analyses
from src.analysis.data import latest_export, load_export_csv, output_dir_for_export
from src.analysis.options import AnalysisOptions
from src.analysis.plot_helpers import configure_matplotlib


GRAPH_CHOICES = (
    "all",
    "trace",
    "layers",
    "histogram",
    "heightmap",
    "surface3d",
    "summary",
)
PLOT_GRAPH_NAMES = {"trace", "layers", "histogram", "heightmap", "surface3d"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze the newest bridge CSV export and generate plots.",
    )
    parser.add_argument(
        "--export-dir",
        default="exports",
        help="Folder containing CSV exports. Defaults to exports.",
    )
    parser.add_argument(
        "--output-dir",
        default="analysis_outputs",
        help="Folder where analysis output folders are written when --save is used.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional explicit CSV path. If omitted, the newest export is used.",
    )
    parser.add_argument(
        "--graphs",
        nargs="+",
        choices=GRAPH_CHOICES,
        default=["all"],
        help=(
            "Graphs/reports to produce. Choices: "
            "all, trace, layers, histogram, heightmap, surface3d, summary."
        ),
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional title used on generated plots/reports.",
    )
    parser.add_argument(
        "--layer",
        type=int,
        default=None,
        help="Restrict 1D graphs/reports to one layer index.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save generated analysis files. Without this, graph windows open interactively and plots are not written to disk.",
    )
    parser.add_argument(
        "--heightmap-tilt-correction",
        action="store_true",
        help="Subtract the best-fit plane before creating the 2D heightmap.",
    )
    parser.add_argument(
        "--heightmap-gaussian-sigma",
        type=float,
        default=0.0,
        help="Gaussian smoothing sigma for the 2D heightmap. 0 disables smoothing.",
    )
    parser.add_argument(
        "--heightmap-force-metadata-size",
        action="store_true",
        help=(
            "Resample rows so the heightmap fills the metadata extents even when "
            "layers have different sample counts."
        ),
    )
    parser.add_argument(
        "--heightmap-z-exaggeration",
        type=float,
        default=1.0,
        help="Multiplier applied to displayed Z/color values in the heightmap.",
    )
    parser.add_argument(
        "--heightmap-contours",
        type=int,
        default=12,
        help="Number of contour lines in the heightmap. Use 0 for no contours.",
    )
    parser.add_argument(
        "--heightmap-grid-x-count",
        type=int,
        default=350,
        help="Interpolated heightmap grid resolution along X.",
    )
    parser.add_argument(
        "--heightmap-grid-y-count",
        type=int,
        default=350,
        help="Interpolated heightmap grid resolution along Y.",
    )
    parser.add_argument(
        "--heightmap-cmap",
        default="turbo",
        help="Matplotlib colormap for heightmaps, such as turbo, viridis, plasma, inferno, or cividis.",
    )
    parser.add_argument(
        "--surface3d-max-grid",
        type=int,
        default=160,
        help="Maximum grid width/height used for interactive 3D surface plotting.",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else latest_export(args.export_dir)
    data = load_export_csv(csv_path)
    output_dir = output_dir_for_export(csv_path, args.output_dir)

    options = AnalysisOptions(
        graphs=_normalize_graphs(args.graphs),
        save=args.save,
        title=args.title,
        layer=args.layer,
        heightmap_tilt_correction=args.heightmap_tilt_correction,
        heightmap_gaussian_sigma=max(0.0, args.heightmap_gaussian_sigma),
        heightmap_force_metadata_size=args.heightmap_force_metadata_size,
        heightmap_z_exaggeration=args.heightmap_z_exaggeration,
        heightmap_contours=max(0, args.heightmap_contours),
        heightmap_grid_x_count=max(2, args.heightmap_grid_x_count),
        heightmap_grid_y_count=max(2, args.heightmap_grid_y_count),
        heightmap_cmap=args.heightmap_cmap,
        surface3d_max_grid=max(20, args.surface3d_max_grid),
    )

    if _matplotlib_required(options):
        try:
            configure_matplotlib()
        except ModuleNotFoundError as error:
            if error.name == "matplotlib":
                raise SystemExit(
                    "Matplotlib is required for analysis plots. Install dependencies "
                    "with install_bridge.bat or run: pip install -r requirements.txt"
                ) from error

            raise

    print(f"Analyzing: {csv_path}")
    print(f"Output:    {output_dir}")
    print(f"Graphs:    {', '.join(sorted(options.graphs))}")

    if options.layer is not None:
        print(f"Layer:     {options.layer}")

    produced_files: list[Path] = []

    for module_info in pkgutil.iter_modules(analyses.__path__):
        if module_info.name.startswith("_"):
            continue

        module = importlib.import_module(f"{analyses.__name__}.{module_info.name}")
        graph_names = set(getattr(module, "GRAPH_NAMES", ()))

        if not graph_names:
            graph_name = getattr(module, "GRAPH_NAME", None)
            graph_names = {graph_name} if graph_name else set()

        if graph_names and not _module_selected(graph_names, options):
            continue

        create_plots = getattr(module, "create_plots", None)

        if create_plots is None:
            continue

        print(f"Running:   {', '.join(sorted(graph_names))}", flush=True)
        files = create_plots(data, output_dir, options)
        produced_files.extend(files)

    if _matplotlib_required(options) and not options.save:
        import matplotlib.pyplot as plt

        print("")
        print("Close the Matplotlib window(s) to finish analysis.")
        plt.show()

    if not produced_files:
        if options.save:
            print("No analysis files were produced.")
        else:
            print("No files saved. Use --save to write analysis outputs to disk.")
        return

    print("")
    print("Produced:")

    for path in produced_files:
        print(f"  {path}")


def _matplotlib_required(options: AnalysisOptions) -> bool:
    return "all" in options.graphs or bool(options.graphs & PLOT_GRAPH_NAMES)


def _normalize_graphs(graphs: list[str]) -> set[str]:
    normalized = {graph.strip().lower() for graph in graphs if graph.strip()}

    if not normalized:
        return {"all"}

    return normalized


def _module_selected(graph_names: set[str], options: AnalysisOptions) -> bool:
    return "all" in options.graphs or bool(graph_names & options.graphs)


if __name__ == "__main__":
    main()
