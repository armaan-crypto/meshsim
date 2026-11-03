"""Terrain from a heightmap or a terrain mesh.

This is the hook for real-world data: a DEM/heightmap exported as .npy, .csv
or a grayscale image, or a scanned surface exported as STL/OBJ/PLY.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .._bullet import p
from ..mesh import load_mesh
from .base import (
    IDENTITY,
    SURFACE_RGBA,
    Environment,
    Param,
    SpawnFrame,
    require_non_negative,
    require_positive,
    set_surface,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def load_heightmap(source) -> np.ndarray:
    """Load a 2D height grid.

    Accepts a 2D array, a ``.npy`` file, a ``.csv``/``.txt`` grid of numbers,
    or a grayscale image (pixel values are normalized to 0..1, so set
    ``height_scale`` to the real height range). Row index maps to +Y and
    column index to +X.
    """
    if isinstance(source, np.ndarray):
        data = source
    else:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Heightmap not found: {path}")
        suffix = path.suffix.lower()
        if suffix == ".npy":
            data = np.load(path)
        elif suffix in (".csv", ".txt"):
            data = np.loadtxt(path, delimiter="," if suffix == ".csv" else None)
        elif suffix in IMAGE_SUFFIXES:
            from PIL import Image

            with Image.open(path) as img:
                gray = np.asarray(img.convert("F"), dtype=float)
            span = gray.max() - gray.min()
            data = (gray - gray.min()) / span if span > 0 else np.zeros_like(gray)
            data = data[::-1]  # image row 0 is the top (+Y edge)
        else:
            raise ValueError(f"Unsupported heightmap format '{suffix}'")
    data = np.asarray(data, dtype=float)
    if data.ndim != 2 or min(data.shape) < 2:
        raise ValueError(f"Heightmap must be a 2D grid of at least 2x2, got shape {data.shape}")
    if not np.all(np.isfinite(data)):
        raise ValueError("Heightmap contains NaN or infinite values")
    return data


class Terrain(Environment):
    name = "terrain"
    description = "Static terrain built from a heightmap grid or a terrain mesh (set exactly one)."
    params = {
        "heightmap": Param(None, "Heightmap: path (.npy, .csv, .txt, image) or a 2D array"),
        "cell_size": Param(1.0, "Heightmap grid spacing, m"),
        "height_scale": Param(1.0, "Multiplier applied to heightmap values to get meters"),
        "mesh": Param(None, "Terrain mesh path (.stl, .obj, .ply), used as a static triangle mesh"),
        "mesh_scale": Param(1.0, "Multiplier applied to terrain mesh coordinates to get meters"),
        "center": Param(True, "Shift the terrain mesh so its XY bounding-box center is at the origin"),
        "friction": Param(1.0, "Terrain friction (multiplied with the object's friction)"),
        "restitution": Param(1.0, "Terrain restitution (multiplied with the object's restitution)"),
        "spawn_x": Param(0.0, "X of the starting point, m"),
        "spawn_y": Param(0.0, "Y of the starting point, m"),
        "spawn_height": Param(0.05, "Gap between the object's lowest point and the terrain below the spawn point, m"),
    }

    def validate(self) -> None:
        has_map = self.heightmap is not None
        has_mesh = self.mesh is not None
        if has_map == has_mesh:
            raise ValueError("terrain: set exactly one of 'heightmap' or 'mesh'")
        require_positive(self, "cell_size", "mesh_scale")
        require_non_negative(self, "friction", "restitution", "spawn_height")
        if has_map:
            self._heights = load_heightmap(self.heightmap) * float(self.height_scale)

    def build(self, client) -> None:
        if self.heightmap is not None:
            body = self._build_heightfield(client)
        else:
            body = self._build_mesh(client)
        set_surface(client, body, self.friction, self.restitution)

    def _build_heightfield(self, client) -> int:
        heights = self._heights
        rows, cols = heights.shape
        collision = client.createCollisionShape(
            p.GEOM_HEIGHTFIELD,
            meshScale=[self.cell_size, self.cell_size, 1.0],
            heightfieldData=heights.flatten().tolist(),
            numHeightfieldRows=cols,
            numHeightfieldColumns=rows,
        )
        # Bullet centers the heightfield vertically on (min + max) / 2.
        z_offset = (heights.min() + heights.max()) / 2
        body = client.createMultiBody(
            baseMass=0, baseCollisionShapeIndex=collision, basePosition=[0, 0, z_offset]
        )
        client.changeVisualShape(body, -1, rgbaColor=SURFACE_RGBA)
        return body

    def _build_mesh(self, client) -> int:
        mesh = load_mesh(self.mesh, scale=float(self.mesh_scale))
        vertices = np.asarray(mesh.vertices, dtype=float)
        if self.center:
            center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2
            vertices = vertices - np.array([center[0], center[1], 0.0])
        indices = np.asarray(mesh.faces, dtype=int).flatten().tolist()
        collision = client.createCollisionShape(
            p.GEOM_MESH,
            vertices=vertices.tolist(),
            indices=indices,
            flags=p.GEOM_FORCE_CONCAVE_TRIMESH,
        )
        visual = client.createVisualShape(
            p.GEOM_MESH, vertices=vertices.tolist(), indices=indices, rgbaColor=SURFACE_RGBA
        )
        return client.createMultiBody(baseMass=0, baseCollisionShapeIndex=collision, baseVisualShapeIndex=visual)

    def surface_height(self, client, x: float, y: float) -> float:
        """Height of the terrain at (x, y), found by casting a ray downward."""
        hit = client.rayTest([x, y, 1e4], [x, y, -1e4])[0]
        if hit[0] < 0:
            raise ValueError(f"terrain: no terrain under the spawn point ({x}, {y})")
        return float(hit[3][2])

    def spawn_frame(self, client) -> SpawnFrame:
        x, y = float(self.spawn_x), float(self.spawn_y)
        z = self.surface_height(client, x, y)
        return SpawnFrame(origin=np.array([x, y, z]), orientation=IDENTITY.copy(), gap=float(self.spawn_height))
