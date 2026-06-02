"""Create top-down and 3D heightmaps from layered scan data."""

from __future__ import annotations

from pathlib import Path

from src.analysis.data import ExportData, ExportSample
from src.analysis.options import AnalysisOptions
from src.analysis.plot_helpers import metadata_title, save_figure


GRAPH_NAME = "heightmap"
SURFACE_GRAPH_NAME = "surface3d"
GRAPH_NAMES = (GRAPH_NAME, SURFACE_GRAPH_NAME)


def create_plots(
    data: ExportData,
    output_dir: Path,
    options: AnalysisOptions,
) -> list[Path]:
    if not options.graph_enabled(GRAPH_NAME) and not options.graph_enabled(SURFACE_GRAPH_NAME):
        return []

    import matplotlib.pyplot as plt
    import numpy as np

    _progress("building physical X/Y/Z points")
    x, y, z, invalid_x, invalid_y, layer_indices = _physical_points_per_layer(
        data,
        force_metadata_size=options.heightmap_force_metadata_size,
    )

    if len(z) == 0:
        return []

    z_label = "Height (mm)"

    if options.heightmap_tilt_correction:
        _progress("removing best-fit tilt plane")
        z, plane = _remove_best_fit_plane(x, y, z)
        z_label = "Tilt-corrected height (mm)"
        _print_plane(plane)

    if options.heightmap_force_metadata_size:
        grid_x_count = max(2, options.heightmap_grid_x_count)
        grid_y_count = max(2, options.heightmap_grid_y_count)
        _progress(f"interpolating points to {grid_x_count} x {grid_y_count} grid")
        X, Y, Z = _interpolate_points_to_grid(
            x,
            y,
            z,
            grid_x_count=grid_x_count,
            grid_y_count=grid_y_count,
        )
    else:
        _progress("building ragged sample-count grid")
        X, Y, Z = _ragged_grid_from_points(x, y, z)
        grid_y_count, grid_x_count = Z.shape

    if options.heightmap_gaussian_sigma > 0:
        _progress(f"applying Gaussian smoothing sigma={options.heightmap_gaussian_sigma:g}")
        Z = _gaussian_smooth_nan_safe(Z, sigma=options.heightmap_gaussian_sigma)
        z_label = z_label.replace("height", "smoothed height")

    print()
    print("Heightmap:")
    print(f"  layers: {len(layer_indices)}")
    print(f"  points: {len(z)}")
    print(f"  grid: {grid_x_count} x {grid_y_count}")
    print(f"  X: {float(np.nanmin(X)):.3f} to {float(np.nanmax(X)):.3f}")
    print(f"  Y: {float(np.nanmin(Y)):.3f} to {float(np.nanmax(Y)):.3f}")
    print(f"  gaussian sigma: {options.heightmap_gaussian_sigma:g}")
    print(f"  z exaggeration: {options.heightmap_z_exaggeration:g}x")

    title_prefix = _heightmap_title_prefix(options)
    figures = []

    if options.graph_enabled(GRAPH_NAME):
        _progress("plotting 2D heightmap")
        top_fig, _ = _plot_top_down_heightmap(
            X,
            Y,
            Z,
            title=f"{title_prefix} top-down heightmap\n{metadata_title(data, options.title)}",
            colorbar_label=z_label,
            contour_levels=options.heightmap_contours,
            cmap_name=options.heightmap_cmap,
            invalid_x=invalid_x,
            invalid_y=invalid_y,
            mark_invalid=options.mark_invalid,
            force_metadata_size=options.heightmap_force_metadata_size,
        )
        figures.append((top_fig, "heightmap_top_down.png"))

    if options.graph_enabled(SURFACE_GRAPH_NAME):
        _progress("plotting 3D surface")
        surface_fig, _ = _plot_3d_heightmap(
            X,
            Y,
            Z,
            title=f"{title_prefix} 3D surface\n{metadata_title(data, options.title)}",
            z_label=z_label,
            z_exaggeration=options.heightmap_z_exaggeration,
            cmap_name=options.heightmap_cmap,
            max_grid=options.surface3d_max_grid,
            invalid_x=invalid_x,
            invalid_y=invalid_y,
            mark_invalid=options.mark_invalid,
        )
        figures.append((surface_fig, "heightmap_3d.png"))

    if not options.save:
        return []

    paths = []

    for fig, filename in figures:
        _progress(f"saving {filename}")
        paths.append(save_figure(fig, output_dir, filename))

    for fig, _ in figures:
        plt.close(fig)

    return paths


def _physical_points_per_layer(
    data: ExportData,
    *,
    force_metadata_size: bool,
):
    import numpy as np

    layers = [
        layer
        for layer in data.layer_indices
        if data.samples_for_layer(layer)
    ]

    if not layers:
        return np.array([]), np.array([]), np.array([]), np.array([]), np.array([]), []

    x_extent, y_extent = _physical_extents(data, layers, force_metadata_size)
    all_x = []
    all_y = []
    all_z = []
    invalid_x = []
    invalid_y = []

    for layer_order, layer in enumerate(layers):
        samples = sorted(data.samples_for_layer(layer), key=_sample_order)
        sample_positions = np.array(
            [
                float(
                    sample.layer_sample_index
                    if sample.layer_sample_index is not None
                    else sample.index
                )
                for sample in samples
            ],
            dtype=float,
        )
        sample_min = float(np.nanmin(sample_positions))
        sample_max = float(np.nanmax(sample_positions))

        if sample_max == sample_min:
            x_values = np.zeros_like(sample_positions)
        elif force_metadata_size:
            x_values = (
                (sample_positions - sample_min)
                / (sample_max - sample_min)
                * x_extent
            )
        else:
            x_values = sample_positions - sample_min

        if len(layers) == 1:
            y_value = 0.0
        else:
            y_value = layer_order / (len(layers) - 1) * y_extent

        y_values = np.full_like(x_values, y_value, dtype=float)
        valid_mask = np.array([sample.valid for sample in samples], dtype=bool)

        if valid_mask.any():
            all_x.append(x_values[valid_mask])
            all_y.append(y_values[valid_mask])
            all_z.append(
                np.array(
                    [
                        sample.value_mm
                        for sample in samples
                        if sample.valid
                    ],
                    dtype=float,
                )
            )

        if (~valid_mask).any():
            invalid_x.append(x_values[~valid_mask])
            invalid_y.append(y_values[~valid_mask])

    return (
        np.concatenate(all_x) if all_x else np.array([]),
        np.concatenate(all_y) if all_y else np.array([]),
        np.concatenate(all_z) if all_z else np.array([]),
        np.concatenate(invalid_x) if invalid_x else np.array([]),
        np.concatenate(invalid_y) if invalid_y else np.array([]),
        layers,
    )


def _physical_extents(
    data: ExportData,
    layers: list[int],
    force_metadata_size: bool,
) -> tuple[float, float]:
    sample_extent = float(max(1, _max_layer_count(data, layers) - 1))
    layer_extent = _layer_extent(data, layers)

    if not force_metadata_size:
        return max(1e-9, sample_extent), max(1e-9, layer_extent)

    scan_width = _positive_metadata_value(data.metadata.get("scan_width"))
    scan_length = _positive_metadata_value(data.metadata.get("scan_length"))
    x_extent = float(scan_width) if scan_width is not None else sample_extent
    y_extent = float(scan_length) if scan_length is not None else layer_extent

    if force_metadata_size and scan_width is None and scan_length is None:
        square_extent = max(x_extent, y_extent, 1.0)
        x_extent = square_extent
        y_extent = square_extent

    return max(1e-9, x_extent), max(1e-9, y_extent)


def _positive_metadata_value(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None

    return float(value)


def _layer_extent(data: ExportData, layers: list[int]) -> float:
    delta_y = data.metadata.get("delta_y")

    if delta_y is not None:
        return abs(float(delta_y)) * max(1, len(layers) - 1)

    return float(max(1, len(layers) - 1))


def _max_layer_count(data: ExportData, layers: list[int]) -> int:
    return max(len(data.samples_for_layer(layer)) for layer in layers)


def _sample_order(sample: ExportSample) -> tuple[int, int]:
    return (
        sample.layer_sample_index if sample.layer_sample_index is not None else sample.index,
        sample.index,
    )


def _remove_best_fit_plane(x, y, z):
    import numpy as np

    valid = ~np.isnan(z)
    A = np.column_stack([x[valid], y[valid], np.ones_like(x[valid])])
    a, b, c = np.linalg.lstsq(A, z[valid], rcond=None)[0]
    plane = a * x + b * y + c
    return z - plane, (float(a), float(b), float(c))


def _interpolate_points_to_grid(
    x,
    y,
    z,
    *,
    grid_x_count: int,
    grid_y_count: int,
):
    import numpy as np

    xi = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), grid_x_count)
    yi = np.linspace(float(np.nanmin(y)), float(np.nanmax(y)), grid_y_count)
    X, Y = np.meshgrid(xi, yi)

    try:
        from scipy.interpolate import griddata
    except ImportError as error:
        raise RuntimeError(
            "SciPy is required for heightmap interpolation. "
            "Install dependencies with install_bridge.bat or run: "
            "pip install -r requirements.txt"
        ) from error

    Z_linear = griddata(
        points=(x, y),
        values=z,
        xi=(X, Y),
        method="linear",
    )
    Z_nearest = griddata(
        points=(x, y),
        values=z,
        xi=(X, Y),
        method="nearest",
    )
    Z = np.where(np.isnan(Z_linear), Z_nearest, Z_linear)
    return X, Y, Z


def _ragged_grid_from_points(x, y, z):
    import numpy as np

    x_unique = np.unique(x)
    y_unique = np.unique(y)
    x_unique.sort()
    y_unique.sort()

    if len(x_unique) == 0 or len(y_unique) == 0:
        return (
            np.empty((0, 0)),
            np.empty((0, 0)),
            np.empty((0, 0)),
        )

    x_lookup = {value: index for index, value in enumerate(x_unique)}
    y_lookup = {value: index for index, value in enumerate(y_unique)}
    Z = np.full((len(y_unique), len(x_unique)), np.nan, dtype=float)

    for x_value, y_value, z_value in zip(x, y, z):
        Z[y_lookup[y_value], x_lookup[x_value]] = z_value

    X, Y = np.meshgrid(x_unique, y_unique)
    return X, Y, Z


def _gaussian_smooth_nan_safe(Z, *, sigma: float):
    import numpy as np

    if sigma <= 0:
        return Z

    try:
        from scipy.ndimage import gaussian_filter
    except ImportError as error:
        raise RuntimeError(
            "SciPy is required for heightmap Gaussian smoothing. "
            "Install dependencies with install_bridge.bat or run: "
            "pip install -r requirements.txt"
        ) from error

    valid_mask = ~np.isnan(Z)
    Z_filled = np.where(valid_mask, Z, 0.0)
    smoothed_values = gaussian_filter(Z_filled, sigma=sigma, mode="nearest")
    smoothed_weights = gaussian_filter(valid_mask.astype(float), sigma=sigma, mode="nearest")
    result = np.full_like(Z, np.nan)
    mask = smoothed_weights > 0
    result[mask] = smoothed_values[mask] / smoothed_weights[mask]
    return result


def _plot_top_down_heightmap(
    X,
    Y,
    Z,
    *,
    title: str,
    colorbar_label: str,
    cmap_name: str,
    contour_levels: int,
    invalid_x,
    invalid_y,
    mark_invalid: bool,
    force_metadata_size: bool,
):
    import matplotlib.pyplot as plt
    import numpy as np

    fig_size = (18, 8) if not force_metadata_size else (12, 10)
    fig, ax = plt.subplots(figsize=fig_size)
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad(color="white")
    image = ax.imshow(
        Z,
        origin="lower",
        aspect="equal" if force_metadata_size else "auto",
        extent=[
            float(np.nanmin(X)),
            float(np.nanmax(X)),
            float(np.nanmin(Y)),
            float(np.nanmax(Y)),
        ],
        cmap=cmap,
    )
    ax.set_title(title)
    ax.set_xlabel("X position (mm)")
    ax.set_ylabel("Y position (mm)")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label(colorbar_label)

    if contour_levels > 0:
        contours = ax.contour(
            X,
            Y,
            Z,
            levels=contour_levels,
            colors="black",
            linewidths=0.4,
        )
        ax.clabel(contours, inline=True, fontsize=7)

    if mark_invalid and len(invalid_x) > 0:
        ax.scatter(
            invalid_x,
            invalid_y,
            color="#d62728",
            marker="x",
            s=18,
            linewidths=0.8,
            label="Invalid sample",
            zorder=4,
        )
        ax.legend(loc="upper right")

    fig.tight_layout()
    return fig, ax


def _plot_3d_heightmap(
    X,
    Y,
    Z,
    *,
    title: str,
    z_label: str,
    z_exaggeration: float,
    cmap_name: str,
    max_grid: int,
    invalid_x,
    invalid_y,
    mark_invalid: bool,
):
    import matplotlib.pyplot as plt
    import numpy as np

    fig = plt.figure(figsize=(18, 11))
    ax = fig.add_subplot(111, projection="3d")
    X, Y, Z = _downsample_surface_grid(X, Y, Z, max_grid=max_grid)
    Z_display = Z * z_exaggeration
    surface = ax.plot_surface(
        X,
        Y,
        Z_display,
        cmap=cmap_name,
        linewidth=0,
        antialiased=True,
    )

    if mark_invalid and len(invalid_x) > 0:
        invalid_z = float(np.nanmin(Z_display))
        ax.scatter(
            invalid_x,
            invalid_y,
            [invalid_z for _ in range(len(invalid_x))],
            color="#d62728",
            marker="x",
            s=20,
            label="Invalid sample",
            depthshade=False,
        )
        ax.legend(loc="best")

    ax.set_title(f"{title} | Z exaggerated {z_exaggeration:g}x")
    ax.set_xlabel("X position (mm)")
    ax.set_ylabel("Y position (mm)")
    ax.set_zlabel(f"{z_label} x {z_exaggeration:g}")

    x_range = float(np.nanmax(X) - np.nanmin(X))
    y_range = float(np.nanmax(Y) - np.nanmin(Y))
    z_range = float(np.nanmax(Z_display) - np.nanmin(Z_display))

    if z_range == 0:
        z_range = 1.0

    ax.set_box_aspect((x_range, y_range, z_range))
    ax.view_init(elev=35, azim=-120)
    colorbar = fig.colorbar(surface, ax=ax, shrink=0.65, pad=0.08)
    colorbar.set_label(z_label)
    fig.tight_layout()
    return fig, ax


def _downsample_surface_grid(X, Y, Z, *, max_grid: int):
    max_dimension = max(X.shape)

    if max_dimension <= max_grid:
        return X, Y, Z

    step = max(1, int(max_dimension / max_grid))
    _progress(
        f"downsampling 3D surface grid from {X.shape[1]} x {X.shape[0]} "
        f"to about {X.shape[1] // step} x {X.shape[0] // step}"
    )
    return X[::step, ::step], Y[::step, ::step], Z[::step, ::step]


def _heightmap_title_prefix(options: AnalysisOptions) -> str:
    parts = []

    if options.heightmap_tilt_correction:
        parts.append("Tilt-corrected")

    if options.heightmap_gaussian_sigma > 0:
        parts.append(f"Gaussian sigma={options.heightmap_gaussian_sigma:g}")

    return " ".join(parts) if parts else "Raw"


def _print_plane(plane: tuple[float, float, float]) -> None:
    a, b, c = plane
    print()
    print("Best-fit plane:")
    print(f"  z = {a:.8f}*x + {b:.8f}*y + {c:.8f}")
    print(f"  X tilt slope: {a:.8f} mm/mm")
    print(f"  Y tilt slope: {b:.8f} mm/mm")


def _progress(message: str) -> None:
    print(f"  ... {message}", flush=True)
