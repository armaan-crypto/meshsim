"""Mesh loading, cleanup and rigid-body mass properties."""

from __future__ import annotations

import importlib.util
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

from ._rotation import quat_from_matrix

MESH_SUFFIXES = {".stl", ".obj", ".ply"}
STEP_SUFFIXES = {".step", ".stp"}
SUPPORTED_SUFFIXES = MESH_SUFFIXES | STEP_SUFFIXES


def load_mesh(source: str | Path | trimesh.Trimesh, scale: float = 1.0) -> trimesh.Trimesh:
    """Load a mesh file (or copy a Trimesh), apply ``scale`` and clean it up.

    Cleanup merges duplicate vertices, drops degenerate and duplicate faces,
    removes unreferenced vertices and makes face winding consistent.
    Multi-part files are merged into one mesh (one rigid body).
    """
    if isinstance(source, trimesh.Trimesh):
        mesh = source.copy()
        name = "<Trimesh>"
    else:
        path = Path(source)
        name = str(path)
        if not path.exists():
            raise FileNotFoundError(f"Mesh file not found: {path}")
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(
                f"Unsupported mesh format '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
            )
        if suffix in STEP_SUFFIXES and importlib.util.find_spec("cascadio") is None:
            raise ImportError(
                "Loading STEP files needs the optional 'cascadio' package. "
                "Install it with: pip install 'meshsim[step]', or convert the file to STL first."
            )
        mesh = trimesh.load(path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError(f"Could not read a triangle mesh from {path}")

    if scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale}")
    if scale != 1.0:
        mesh.apply_scale(scale)

    mesh = clean_mesh(mesh)
    if len(mesh.faces) == 0:
        raise ValueError(f"Mesh {name} has no valid triangles after cleanup")
    return mesh


def clean_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mesh = mesh.copy()
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh)
    return mesh


@dataclass
class BodyProperties:
    """Rigid-body data derived from a mesh.

    The body frame has its origin at the center of mass and its axes along the
    principal axes of inertia, so the inertia tensor is diagonal in it.
    """

    mass: float
    volume: float
    density: float
    watertight: bool
    center_of_mass: np.ndarray
    """Center of mass in the original mesh coordinates (after scaling)."""
    inertia_diagonal: np.ndarray
    """Principal moments of inertia, kg*m^2."""
    body_to_mesh: np.ndarray
    """Quaternion [x, y, z, w] rotating body-frame vectors into mesh-frame vectors."""
    vertices_body: np.ndarray
    """Mesh vertices expressed in the body frame."""
    faces: np.ndarray
    hull_vertices_body: np.ndarray
    """Convex hull vertices in the body frame (used as the collision shape)."""
    extents: np.ndarray
    """Axis-aligned bounding box size in the mesh frame, meters."""

    def summary(self) -> dict:
        return {
            "mass_kg": self.mass,
            "volume_m3": self.volume,
            "density_kg_m3": self.density,
            "watertight": self.watertight,
            "extents_m": self.extents.tolist(),
            "center_of_mass_m": self.center_of_mass.tolist(),
            "principal_inertia_kg_m2": self.inertia_diagonal.tolist(),
            "triangles": int(len(self.faces)),
            "collision_shape": "convex_hull",
        }


def compute_body_properties(
    mesh: trimesh.Trimesh, density: float = 1000.0, mass: float | None = None
) -> BodyProperties:
    """Compute mass, center of mass and principal inertia for a mesh.

    Non-watertight meshes have no well-defined volume, so their convex hull is
    used for mass properties instead and a warning is issued.
    """
    watertight = bool(mesh.is_watertight and mesh.volume > 0)
    solid = mesh
    if not watertight:
        warnings.warn(
            "Mesh is not watertight; using its convex hull to compute volume, mass and inertia.",
            stacklevel=2,
        )
        solid = mesh.convex_hull
    volume = float(solid.volume)
    if volume <= 0:
        raise ValueError("Mesh has zero volume; cannot compute mass properties")

    if mass is not None:
        density = mass / volume
    total_mass = density * volume

    com = np.asarray(solid.center_mass, dtype=float)
    # trimesh reports the inertia tensor about the center of mass for unit density.
    inertia = np.asarray(solid.moment_inertia, dtype=float) / solid.density * density
    moments, axes = np.linalg.eigh(inertia)
    rotation = axes  # columns are principal axes in mesh coordinates
    if np.linalg.det(rotation) < 0:
        rotation[:, 2] *= -1
    moments = np.maximum(moments, 1e-12)

    vertices_body = (np.asarray(mesh.vertices) - com) @ rotation
    hull_body = (np.asarray(mesh.convex_hull.vertices) - com) @ rotation
    return BodyProperties(
        mass=float(total_mass),
        volume=volume,
        density=float(density),
        watertight=watertight,
        center_of_mass=com,
        inertia_diagonal=moments,
        body_to_mesh=quat_from_matrix(rotation),
        vertices_body=vertices_body,
        faces=np.asarray(mesh.faces),
        hull_vertices_body=hull_body,
        extents=np.asarray(mesh.extents, dtype=float),
    )
