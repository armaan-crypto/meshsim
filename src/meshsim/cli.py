"""Command-line interface: ``meshsim run model.stl --env ramp --duration 5``."""

from __future__ import annotations

import argparse
import sys
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

    sub.add_parser("envs", help="List environments and their parameters")
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
    for kind, path in paths.items():
        print(f"  wrote {kind:<10} {path}")
    return 0


def _envs() -> int:
    for name, cls in sorted(ENVIRONMENTS.items()):
        print(f"{name}: {cls.description}")
        for key, spec in cls.params.items():
            print(f"    {key:<16} default={spec.default!r:<8} {spec.help}")
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        return _envs()
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
