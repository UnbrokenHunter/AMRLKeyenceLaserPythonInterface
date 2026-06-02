"""Create top-down and 3D heightmaps from layered scan data."""

from __future__ import annotations

from pathlib import Path

from src.analysis.data import ExportData, ExportSample
from src.analysis.options import AnalysisOptions
from src.analysis.plot_helpers import metadata_title, save_figure


GRAPH_NAME = "heightmap"
SURFACE_GRAPH_NAME = "surface3d"


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
    x, y, z, layer_indices = _physical_points_per_layer(
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
        if data.valid_samples_for_layer(layer)
    ]

    if not layers:
        return np.array([]), np.array([]), np.array([]), []

    x_extent, y_extent = _physical_extents(data, layers, force_metadata_size)
    all_x = []
    all_y = []
    all_z = []

    for layer_order, layer in enumerate(layers):
        samples = sorted(
            data.valid_samples_for_layer(layer),
            key=_sample_order,
        )
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
        z_values = np.array([sample.value_mm for sample in samples], dtype=float)

        sample_min = float(np.nanmin(sample_positions))
        sample_max = float(np.nanmax(sample_positions))

        if sample_max == sample_min:
            x_values = np.zeros_like(sample_positions)
        else:
            x_values = (
                (sample_positions - sample_min)
                / (sample_max - sample_min)
                * x_extent
            )

        if len(layers) == 1:
            y_value = 0.0
        else:
            y_value = layer_order / (len(layers) - 1) * y_extent

        y_values = np.full_like(x_values, y_value, dtype=float)

        all_x.append(x_values)
        all_y.append(y_values)
        all_z.append(z_values)

    return (
        np.concatenate(all_x),
        np.concatenate(all_y),
        np.concatenate(all_z),
        layers,
    )


def _physical_extents(
    data: ExportData,
    layers: list[int],
    force_metadata_size: bool,
) -> tuple[float, float]:
    scan_width = data.metadata.get("scan_width")
    scan_length = data.metadata.get("scan_length")
    sample_extent = float(max(1, _max_layer_count(data, layers) - 1))
    layer_extent = _layer_extent(data, layers)

    x_extent = float(scan_width) if scan_width is not None else sample_extent
    y_extent = float(scan_length) if scan_length is not None else layer_extent

    if force_metadata_size and scan_width is None and scan_length is None:
        square_extent = max(x_extent, y_extent, 1.0)
        x_extent = square_extent
        y_extent = square_extent

    return max(1e-9, x_extent), max(1e-9, y_extent)


def _layer_extent(data: ExportData, layers: list[int]) -> float:
    delta_y = data.metadata.get("delta_y")

    if delta_y is not None:
        return abs(float(delta_y)) * max(1, len(layers) - 1)

    return float(max(1, len(layers) - 1))


def _max_layer_count(data: ExportData, layers: list[int]) -> int:
    return max(len(data.valid_samples_for_layer(layer)) for layer in layers)


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
    except ImportError:
        _progress("SciPy not installed; using slower nearest-neighbor fallback")
        return X, Y, _nearest_grid(x, y, z, X, Y)

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


def _nearest_grid(x, y, z, X, Y):
    import numpy as np

    Z = np.empty_like(X, dtype=float)
    points = np.column_stack([x, y])
    flat_targets = np.column_stack([X.ravel(), Y.ravel()])
    chunk_size = 2000
    values = []

    for start in range(0, len(flat_targets), chunk_size):
        if start % (chunk_size * 10) == 0:
            percent = min(100, int(start / max(1, len(flat_targets)) * 100))
            _progress(f"nearest-neighbor fallback {percent}%")

        targets = flat_targets[start : start + chunk_size]
        distances = (
            (targets[:, None, 0] - points[None, :, 0]) ** 2
            + (targets[:, None, 1] - points[None, :, 1]) ** 2
        )
        nearest = np.argmin(distances, axis=1)
        values.append(z[nearest])

    Z.ravel()[:] = np.concatenate(values)
    return Z


def _gaussian_smooth_nan_safe(Z, *, sigma: float):
    import numpy as np

    if sigma <= 0:
        return Z

    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        return _gaussian_smooth_fallback(Z, sigma=sigma)

    valid_mask = ~np.isnan(Z)
    Z_filled = np.where(valid_mask, Z, 0.0)
    smoothed_values = gaussian_filter(Z_filled, sigma=sigma, mode="nearest")
    smoothed_weights = gaussian_filter(valid_mask.astype(float), sigma=sigma, mode="nearest")
    result = np.full_like(Z, np.nan)
    mask = smoothed_weights > 0
    result[mask] = smoothed_values[mask] / smoothed_weights[mask]
    return result


def _gaussian_smooth_fallback(Z, *, sigma: float):
    import numpy as np

    kernel = _gaussian_kernel(sigma)
    result = Z.copy()

    for axis in (1, 0):
        result = np.apply_along_axis(
            lambda line: _smooth_line_nan_safe(line, kernel),
            axis,
            result,
        )

    return result


def _gaussian_kernel(sigma: float):
    import numpy as np

    radius = max(1, int(round(sigma * 3)))
    offsets = np.arange(-radius, radius + 1, dtype=float)
    weights = np.exp(-((offsets * offsets) / (2 * sigma * sigma)))
    return weights / weights.sum()


def _smooth_line_nan_safe(line, kernel):
    import numpy as np

    radius = len(kernel) // 2
    smoothed = np.full_like(line, np.nan, dtype=float)

    for index, value in enumerate(line):
        weighted_sum = 0.0
        weight_sum = 0.0

        for offset, weight in enumerate(kernel):
            source_index = index + offset - radius

            if not 0 <= source_index < len(line):
                continue

            source_value = line[source_index]

            if np.isnan(source_value):
                continue

            weighted_sum += source_value * weight
            weight_sum += weight

        if weight_sum > 0:
            smoothed[index] = weighted_sum / weight_sum

    return smoothed


def _plot_top_down_heightmap(
    X,
    Y,
    Z,
    *,
    title: str,
    colorbar_label: str,
    cmap_name: str,
    contour_levels: int,
):
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(12, 10))
    image = ax.imshow(
        Z,
        origin="lower",
        aspect="equal",
        extent=[
            float(np.nanmin(X)),
            float(np.nanmax(X)),
            float(np.nanmin(Y)),
            float(np.nanmax(Y)),
        ],
        cmap=cmap_name,
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
