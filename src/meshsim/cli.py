"""Command-line interface: ``meshsim run model.stl --env ramp --duration 5``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from ._meta import PROJECT_NAME, __version__
from .config import SimConfig
from .environments import ENVIRONMENTS


def _parse_env_param(text: str) -> tuple[str, Any]:
    if "=" not in text:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {text!r}")
    key, value = text.split("=", 1)
    return key.strip(), yaml.safe_load(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROJECT_NAME, description="Physics-based testing for 3D designs.")
    parser.add_argument("--version", action="version", version=f"{PROJECT_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Simulate a mesh in an environment and write results")
    run.add_argument("model", help="Mesh file (.stl, .obj, .ply; .step/.stp with the 'step' extra)")
    run.add_argument("--config", "-c", help="YAML config file; CLI flags override it")
    run.add_argument("--env", "-e", choices=sorted(ENVIRONMENTS), help="Environment (default: flat)")
    run.add_argument(
        "--env-param", "-p", action="append", default=[], type=_parse_env_param, metavar="KEY=VALUE",
        help="Environment parameter, repeatable, e.g. -p angle=30 -p friction=0.4",
    )
    run.add_argument("--duration", "-d", type=float, help="Simulated seconds (default: 5)")
    run.add_argument("--timestep", type=float, help="Physics step in seconds (default: 1/240)")
    run.add_argument("--gravity", type=float, help="Gravity magnitude in m/s^2 (default: 9.81)")
    run.add_argument("--scale", type=float, help="Mesh unit to meters, e.g. 0.001 for mm (default: 1)")
    run.add_argument("--mass", type=float, help="Mass in kg (overrides density)")
    run.add_argument("--density", type=float, help="Density in kg/m^3 (default: 1000)")
    run.add_argument("--friction", type=float, help="Object friction coefficient (default: 0.5)")
    run.add_argument("--restitution", type=float, help="Object restitution 0..1 (default: 0.2)")
    run.add_argument("--orientation", type=float, nargs=3, metavar=("ROLL", "PITCH", "YAW"),
                     help="Initial orientation in degrees")
    run.add_argument("--velocity", type=float, nargs=3, metavar=("VX", "VY", "VZ"), help="Initial velocity, m/s")
    run.add_argument("--out", "-o", help=f"Output directory (default: {PROJECT_NAME}_output)")
    run.add_argument("--render", action="store_true", default=None, help="Also write an animation")
    run.add_argument("--render-format", choices=["gif", "mp4"], help="Animation format (default: gif)")
    run.add_argument("--fps", type=int, help="Animation frames per second (default: 30)")
    run.add_argument("--no-plot", action="store_true", help="Skip plot.png")
    run.add_argument("--tip-threshold", type=float, help="Final tilt in degrees counted as tipped over (default: 45)")

    stability = sub.add_parser("stability", help="Compute static tip-over angles without running a simulation")
    stability.add_argument("model", help="Mesh file (.stl, .obj, .ply; .step/.stp with the 'step' extra)")
    stability.add_argument("--scale", type=float, default=1.0, help="Mesh unit to meters (default: 1)")
    stability.add_argument("--mass", type=float, help="Part mass in kg (overrides density)")
    stability.add_argument("--density", type=float, default=1000.0, help="Density in kg/m^3 (default: 1000)")
    stability.add_argument("--orientation", type=float, nargs=3, default=(0.0, 0.0, 0.0),
                           metavar=("ROLL", "PITCH", "YAW"), help="Resting orientation in degrees")
    stability.add_argument("--add-mass", type=float, metavar="KG", help="One extra point mass, e.g. a phone in a stand")
    stability.add_argument("--at", type=float, nargs=3, metavar=("X", "Y", "Z"),
                           help="Where the extra mass sits: meters, in the part's own axes after --scale")
    stability.add_argument("--directions", type=int, default=8, help="Tilt directions to report (default: 8)")
    stability.add_argument("--list-poses", action="store_true",
                           help="Also list resting orientations and their likelihood (needs the 'poses' extra)")
    stability.add_argument("--json", metavar="FILE", help="Also write the results to a JSON file")

    sub.add_parser("envs", help="List environments and their parameters")
    sub.add_parser("mcp", help="Serve meshsim's tools to MCP clients over stdio (needs the 'mcp' extra)")
    return parser


def _run(args: argparse.Namespace) -> int:
    from .simulation import Simulation  # import here so `--help` stays fast

    config = SimConfig.load(args.config)
    overrides = {
        "env": args.env,
        "env_params": dict(args.env_param) if args.env_param else None,
        "duration": args.duration,
        "timestep": args.timestep,
        "gravity": args.gravity,
        "scale": args.scale,
        "mass": args.mass,
        "density": args.density,
        "friction": args.friction,
        "restitution": args.restitution,
        "initial_orientation": args.orientation,
        "initial_velocity": args.velocity,
        "output_dir": args.out,
        "render": args.render,
        "render_format": args.render_format,
        "render_fps": args.fps,
        "plot": False if args.no_plot else None,
        "tip_threshold": args.tip_threshold,
    }
    sim = Simulation(args.model, config, **overrides)
    print(f"Simulating {args.model} in '{sim.environment.name}' for {sim.config.duration:g} s "
          f"(mass {sim.body.mass:.4g} kg)...")
    result = sim.run()
    paths = result.save()

    m = result.metrics
    def fmt(value: Any, unit: str) -> str:
        return "n/a" if value is None else f"{value:.4g} {unit}"

    print(f"  peak acceleration     {m['peak_acceleration_m_s2']:.4g} m/s^2 ({m['peak_acceleration_g']:.3g} g)")
    print(f"  peak impact velocity  {fmt(m['peak_impact_velocity_m_s'], 'm/s')}")
    print(f"  settle time           {fmt(m['settle_time_s'], 's') if m['settled'] else 'did not settle'}")
    print(f"  total distance        {m['total_distance_m']:.4g} m")
    print("  final position        [" + ", ".join(f"{v:.4g}" for v in m["final_position_m"]) + "] m")
    tipped = "tipped over" if m["tipped_over"] else "did not tip over"
    print(f"  max tilt              {m['max_tilt_deg']:.3g} deg ({tipped})")
    for kind, path in paths.items():
        print(f"  wrote {kind:<10} {path}")
    return 0


def _stability(args: argparse.Namespace) -> int:
    from .mesh import load_mesh
    from .output import write_json
    from .stability import stable_poses, tip_angles

    mesh = load_mesh(args.model, scale=args.scale)
    load = {"density": args.density, "mass": args.mass, "add_mass": args.add_mass, "add_mass_at": args.at}
    result = tip_angles(mesh, orientation=args.orientation, directions=args.directions, **load)
    poses = stable_poses(mesh, **load) if args.list_poses else None

    if result.stable:
        print(f"  min tip angle       {result.min_tip_angle_deg:.3g} deg, "
              f"toward azimuth {result.min_tip_azimuth_deg:.3g} deg")
    else:
        print("  min tip angle       0 deg: the part cannot rest in this pose "
              "(no support area, or its center of mass is outside it)")
    print(f"  COM height          {result.com_height_m:.4g} m")
    print("  support polygon     " + " x ".join(f"{v:.4g}" for v in result.support_extents_m)
          + f" m, area {result.support_area_m2:.4g} m^2")
    print(f"  total mass          {result.total_mass_kg:.4g} kg")
    if result.stable:
        print("  tip angle by direction (azimuth from +X toward +Y, the way it tips):")
        for direction in result.directions:
            print(f"    {direction['azimuth_deg']:>6.1f} deg  {direction['tip_angle_deg']:.3g} deg")
    print("  Static estimate: a push or a bounce can tip it sooner. Test that with a flat run and --velocity.")
    if poses is not None:
        print("  resting poses, likeliest first:")
        for pose in poses:
            orientation = " ".join(f"{v:.4g}" for v in pose["orientation_deg"])
            print(f"    {pose['probability']:>6.1%}  --orientation {orientation}")
    if args.json:
        report = {
            "tool": PROJECT_NAME,
            "version": __version__,
            "model": {"source": args.model, "scale": args.scale},
            "orientation_deg": list(args.orientation),
            "add_mass_kg": args.add_mass,
            "add_mass_at_m": args.at,
            "stability": result.to_dict(),
        }
        if poses is not None:
            report["stable_poses"] = poses
        print(f"  wrote {write_json(report, Path(args.json))}")
    return 0


def _envs() -> int:
    for name, cls in sorted(ENVIRONMENTS.items()):
        print(f"{name}: {cls.description}")
        for key, spec in cls.params.items():
            print(f"    {key:<16} default={spec.default!r:<8} {spec.help}")
        print()
    return 0


def _mcp() -> int:
    from .mcp_server import serve

    serve()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        if args.command == "stability":
            return _stability(args)
        if args.command == "mcp":
            return _mcp()
        return _envs()
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
