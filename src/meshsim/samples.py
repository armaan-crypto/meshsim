"""Small sample meshes generated in code, used by the examples and tests."""

from __future__ import annotations

import numpy as np
import trimesh


def make_cube(size: float = 0.2) -> trimesh.Trimesh:
    """A cube with edge length ``size`` meters, centered at the origin."""
    return trimesh.creation.box(extents=(size, size, size))


def make_wedge(length: float = 0.3, width: float = 0.2, height: float = 0.15) -> trimesh.Trimesh:
    """A right-triangle prism (a door-stop wedge) resting on the XY plane.

    The sloped face rises from x=0 to x=length; the cross-section is in the XZ plane.
    """
    l, w, h = length, width, height
    vertices = np.array(
        [
            [0, 0, 0], [l, 0, 0], [l, 0, h],  # front triangle (y=0)
            [0, w, 0], [l, w, 0], [l, w, h],  # back triangle (y=w)
        ],
        dtype=float,
    )
    faces = np.array(
        [
            [0, 2, 1],  # front
            [3, 4, 5],  # back
            [0, 1, 4], [0, 4, 3],  # bottom
            [1, 2, 5], [1, 5, 4],  # vertical back face (x=l)
            [0, 3, 5], [0, 5, 2],  # sloped face
        ]
    )
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh
