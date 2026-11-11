"""Static tip-over analysis: how far a part can tilt before its weight tips it.

This is geometry, not simulation. A part on a tilting surface tips when the
vertical line through its center of mass leaves its support polygon, which
gives tan(angle) = distance to the polygon edge / center-of-mass height.
It ignores dynamics: a push or a bounce can tip a part below this angle.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any

import numpy as np
import trimesh
from scipy.spatial import ConvexHull

from ._rotation import quat_from_euler_deg, quat_from_matrix, quat_to_euler_deg, quat_to_matrix
from .mesh import compute_body_properties

SUPPORT_TOLERANCE = 1e-3
"""Hull vertices this close to the lowest point count as touching, as a fraction of the part's largest extent."""


@dataclass
class TipResult:
    """Tip-over angles of a posed part. Lengths are meters and angles are degrees.

    Azimuths are measured in the posed frame, from +X toward +Y, and name the
    direction the part tips toward (the downhill direction of the tilted surface).
    """

    stable: bool
    """False if the part cannot rest in this pose: it has no support area or its center of mass is outside it."""
    min_tip_angle_deg: float
    """Smallest tilt that tips the part, over all directions. 0 when not stable."""
    min_tip_azimuth_deg: float
    directions: list[dict[str, float]]
    """Tip angle for each evenly spaced sample direction."""
    center_of_mass_m: np.ndarray
    """Center of mass in the posed frame, including any added mass."""
    com_height_m: float
    """Height of the center of mass above the lowest point of the part."""
    support_polygon_m: np.ndarray
    """Support polygon corners (x, y) in the posed frame, counter-clockwise when it has an area."""
    support_area_m2: float
    support_extents_m: np.ndarray
    total_mass_kg: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "stable": self.stable,
            "min_tip_angle_deg": self.min_tip_angle_deg,
            "min_tip_azimuth_deg": self.min_tip_azimuth_deg,
            "directions": self.directions,
            "center_of_mass_m": self.center_of_mass_m.tolist(),
            "com_height_m": self.com_height_m,
            "support_polygon_m": self.support_polygon_m.tolist(),
            "support_area_m2": self.support_area_m2,
            "support_extents_m": self.support_extents_m.tolist(),
            "total_mass_kg": self.total_mass_kg,
        }


def _combined_com(
    mesh: trimesh.Trimesh,
    com: Any,
    density: float,
    mass: float | None,
    add_mass: float | None,
    add_mass_at: Any,
) -> tuple[np.ndarray, float]:
    """Center of mass in mesh coordinates and total mass, including one optional point mass."""
    if (add_mass is None) != (add_mass_at is None):
        raise ValueError("add_mass and add_mass_at must be given together")
    if add_mass is not None and add_mass <= 0:
        raise ValueError(f"add_mass must be > 0, got {add_mass}")

    body = compute_body_properties(mesh, density=density, mass=mass)
    center = body.center_of_mass if com is None else np.asarray(com, dtype=float)
    if center.shape != (3,):
        raise ValueError("com must be three numbers (x, y, z)")
    if add_mass is None:
        return center, body.mass

    point = np.asarray(add_mass_at, dtype=float)
    if point.shape != (3,):
        raise ValueError("add_mass_at must be three numbers (x, y, z)")
    total = body.mass + add_mass
    return (body.mass * center + add_mass * point) / total, total


def tip_angles(
    mesh: trimesh.Trimesh,
    orientation: Any = (0.0, 0.0, 0.0),
    com: Any = None,
    directions: int = 8,
    density: float = 1000.0,
    mass: float | None = None,
    add_mass: float | None = None,
    add_mass_at: Any = None,
) -> TipResult:
    """Compute the static tip-over angles of ``mesh`` resting in a given pose.

    ``mesh`` must already be in meters. ``orientation`` is roll, pitch, yaw in
    degrees, as for ``initial_orientation``. ``com`` overrides the computed center
    of mass. ``add_mass`` (kg) at ``add_mass_at`` adds one point mass such as a
    phone in a stand. ``com`` and ``add_mass_at`` are in mesh coordinates, meters.
    Density or mass only matter when a point mass is added.

    The minimum angle is exact: it comes from the nearest polygon edge, not from
    the sampled ``directions``.
    """
    if directions < 1:
        raise ValueError(f"directions must be >= 1, got {directions}")
    center, total_mass = _combined_com(mesh, com, density, mass, add_mass, add_mass_at)

    rotation = quat_to_matrix(quat_from_euler_deg(orientation))
    hull = np.asarray(mesh.convex_hull.vertices) @ rotation.T
    lowest = float(hull[:, 2].min())
    posed_com = rotation @ center
    height = float(posed_com[2] - lowest)
    tolerance = SUPPORT_TOLERANCE * float(np.max(mesh.extents))
    if height <= 0:
        raise ValueError("The center of mass is at or below the lowest point of the part")
    if add_mass is not None and (rotation @ np.asarray(add_mass_at, dtype=float))[2] < lowest - tolerance:
        raise ValueError("add_mass_at is below the surface the part rests on")

    points = hull[hull[:, 2] <= lowest + tolerance, :2]
    azimuths = np.arange(directions) * 360.0 / directions
    polygon, area, normals, distances = _support_polygon(points, posed_com[:2])
    stable = normals is not None and bool(np.min(distances) > 0)
    if stable:
        rays = np.column_stack([np.cos(np.radians(azimuths)), np.sin(np.radians(azimuths))])
        reach = np.array([_ray_distance(ray, normals, distances) for ray in rays])
        angles = np.degrees(np.arctan2(reach, height))
        nearest = int(np.argmin(distances))
        min_angle = float(np.degrees(np.arctan2(distances[nearest], height)))
        min_azimuth = float(np.degrees(np.arctan2(normals[nearest, 1], normals[nearest, 0])) % 360.0)
    else:
        angles = np.zeros(directions)
        min_angle = 0.0
        min_azimuth = 0.0

    return TipResult(
        stable=stable,
        min_tip_angle_deg=min_angle,
        min_tip_azimuth_deg=min_azimuth,
        directions=[
            {"azimuth_deg": float(az), "tip_angle_deg": float(angle)}
            for az, angle in zip(azimuths, angles, strict=True)
        ],
        center_of_mass_m=posed_com,
        com_height_m=height,
        support_polygon_m=polygon,
        support_area_m2=area,
        support_extents_m=points.max(axis=0) - points.min(axis=0),
        total_mass_kg=float(total_mass),
    )


def _support_polygon(
    points: np.ndarray, com_xy: np.ndarray
) -> tuple[np.ndarray, float, np.ndarray | None, np.ndarray | None]:
    """Convex polygon of the contact points: corners, area, edge normals, COM-to-edge distances.

    A part resting on a single point or line has no area, so normals and
    distances are None. Distances are negative for edges the COM lies outside of.
    """
    spread = np.linalg.svd(points - points.mean(axis=0), compute_uv=False)
    if len(points) < 3 or spread[1] <= 1e-9 * max(spread[0], 1e-12):
        return points, 0.0, None, None
    hull = ConvexHull(points)
    # Qhull facet equations are n.x + b <= 0 inside, with n a unit outward normal.
    normals, offsets = hull.equations[:, :2], hull.equations[:, 2]
    return points[hull.vertices], float(hull.volume), normals, -(normals @ com_xy + offsets)


def _ray_distance(ray: np.ndarray, normals: np.ndarray, distances: np.ndarray) -> float:
    """Distance from an interior point to the polygon boundary along a unit vector."""
    closing = normals @ ray
    return float(np.min(distances[closing > 1e-12] / closing[closing > 1e-12]))


def stable_poses(
    mesh: trimesh.Trimesh,
    com: Any = None,
    density: float = 1000.0,
    mass: float | None = None,
    add_mass: float | None = None,
    add_mass_at: Any = None,
) -> list[dict[str, Any]]:
    """Resting orientations of ``mesh`` and how likely a random landing ends in each, likeliest first.

    Each ``orientation_deg`` is roll, pitch, yaw and can be passed straight to
    ``--orientation`` or ``tip_angles``. Needs the optional ``networkx`` package.
    """
    if importlib.util.find_spec("networkx") is None:
        raise ImportError(
            "Listing stable poses needs the optional 'networkx' package. "
            "Install it with: pip install 'meshsim[poses]'"
        )
    center, _ = _combined_com(mesh, com, density, mass, add_mass, add_mass_at)
    transforms, probabilities = mesh.compute_stable_poses(center_mass=center)
    poses = [
        {
            "orientation_deg": (np.round(quat_to_euler_deg(quat_from_matrix(transform[:3, :3])), 6) + 0.0).tolist(),
            "probability": float(probability),
        }
        for transform, probability in zip(transforms, probabilities, strict=True)
    ]
    return sorted(poses, key=lambda pose: -pose["probability"])
