"""Command-line options shared by analysis modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisOptions:
    graphs: set[str]
    save: bool = False
    title: str | None = None
    layer: int | None = None
    mark_invalid: bool = False
    min_height: float | None = None
    max_height: float | None = None
    drop_filtered: bool = False
    filtered_sample_count: int = 0
    dropped_sample_count: int = 0
    original_sample_count: int | None = None
    heightmap_tilt_correction: bool = False
    heightmap_gaussian_sigma: float = 0.0
    heightmap_force_metadata_size: bool = False
    heightmap_z_exaggeration: float = 1.0
    heightmap_contours: int = 12
    heightmap_grid_x_count: int = 350
    heightmap_grid_y_count: int = 350
    heightmap_cmap: str = "turbo"
    surface3d_max_grid: int = 160

    def graph_enabled(self, graph_name: str) -> bool:
        return "all" in self.graphs or graph_name in self.graphs
