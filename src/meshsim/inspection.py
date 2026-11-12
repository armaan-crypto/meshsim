"""Check a mesh before simulating it: likely units, closedness, concavity, flat bottom."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np

from .mesh import load_mesh

UNIT_SCALES = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254}


def guess_units(max_extent: float) -> tuple[str, str]:
    """Return (likely unit, confidence note) from the largest raw dimension."""
    if max_extent > 50:
        return "mm", "large raw numbers; CAD exports in millimeters look like this"
    if max_extent >= 5:
        return "ambiguous", "could be mm (small part), cm, or inches; check with the user or the file's source"
    if max_extent >= 0.001:
        return "m", "plausible as meters"
    return "ambiguous", "tiny raw numbers; units may be meters for a very small part, or the export is wrong"


def flat_bottom_fraction(mesh) -> float:
    """Share of the bottom (min-Z) footprint covered by faces pointing straight down."""
    z_min = mesh.bounds[0][2]
    tol = 1e-6 * max(mesh.extents.max(), 1e-9)
    down = mesh.face_normals[:, 2] < -0.999
    on_bottom = np.all(np.abs(mesh.vertices[mesh.faces][:, :, 2] - z_min) < tol, axis=1)
    area = mesh.area_faces[down & on_bottom].sum()
    footprint = mesh.extents[0] * mesh.extents[1]
    return float(area / footprint) if footprint > 0 else 0.0


def inspect_mesh(path: str | Path, scale: float | None = None) -> dict[str, Any]:
    """Describe a mesh file. With ``scale``, also report its size in meters at that scale."""
    if scale is not None and scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mesh = load_mesh(path)
    extents = mesh.extents.astype(float)
    unit, note = guess_units(float(extents.max()))
    watertight = bool(mesh.is_watertight and mesh.volume > 0)
    hull_volume = float(mesh.convex_hull.volume)
    solidity = float(mesh.volume / hull_volume) if watertight and hull_volume > 0 else None
    info: dict[str, Any] = {
        "file": str(path),
        "triangles": int(len(mesh.faces)),
        "raw_extents": extents.round(6).tolist(),
        "extents_if_units": {u: (extents * s).round(4).tolist() for u, s in UNIT_SCALES.items()},
        "likely_units": unit,
        "units_note": note,
        "suggested_scale": UNIT_SCALES.get(unit),
        "watertight": watertight,
        "solidity": None if solidity is None else round(solidity, 3),
        "concave": solidity is not None and solidity < 0.9,
        "flat_bottom_fraction": round(flat_bottom_fraction(mesh), 3),
    }
    if scale is not None:
        info["extents_at_scale_m"] = (extents * scale).round(6).tolist()
    return info


def describe_inspection(info: dict[str, Any]) -> str:
    """Format the result of ``inspect_mesh`` as readable text."""
    lines = [f"{info['file']}: {info['triangles']} triangles"]
    lines.append(f"  raw size (file units): {info['raw_extents']}")
    for unit, ext in info["extents_if_units"].items():
        lines.append(f"    if {unit:<2}: {ext} m")
    scale = info["suggested_scale"]
    lines.append(
        f"  likely units: {info['likely_units']} ({info['units_note']})"
        + (f" -> use --scale {scale:g}" if scale not in (None, 1.0) else "")
    )
    if info["watertight"]:
        lines.append("  closed mesh: yes (mass and inertia use the real shape)")
    else:
        lines.append("  closed mesh: NO (mass and inertia fall back to the convex hull)")
    if info["concave"]:
        lines.append(
            f"  concave: yes (fills {info['solidity']:.0%} of its convex hull); it will collide as its hull, "
            "so hollows and slots behave as if filled"
        )
    if info["flat_bottom_fraction"] > 0.5:
        lines.append(
            "  flat bottom: yes; for drop tests with restitution > 0 add a small tilt "
            "(--orientation 4 3 0) to avoid spurious spin from a perfectly flat landing"
        )
    return "\n".join(lines)
