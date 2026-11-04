"""Inspect a mesh before simulating it with meshsim.

Prints size in the file's raw units with candidate unit interpretations, whether
the mesh is closed, how concave it is, and whether it has a large flat bottom.
Run it with the Python environment that has meshsim installed:

    python inspect_mesh.py part.stl [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings

import numpy as np

try:
    from meshsim import load_mesh
except ImportError:
    sys.exit("meshsim is not installed in this Python environment. See the meshsim skill's install steps.")

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


def inspect(path: str) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mesh = load_mesh(path)
    extents = mesh.extents.astype(float)
    max_extent = float(extents.max())
    unit, note = guess_units(max_extent)
    watertight = bool(mesh.is_watertight and mesh.volume > 0)
    hull_volume = float(mesh.convex_hull.volume)
    solidity = float(mesh.volume / hull_volume) if watertight and hull_volume > 0 else None
    return {
        "file": path,
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


def describe(info: dict) -> str:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mesh")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args()
    info = inspect(args.mesh)
    print(json.dumps(info, indent=2) if args.json else describe(info))


if __name__ == "__main__":
    main()
