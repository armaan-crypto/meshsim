"""MCP server exposing meshsim as tools: ``meshsim mcp`` (needs the 'mcp' extra).

The tool functions are plain Python and do not import the MCP SDK; only
``build_server`` does. Tools read the mesh file they are given (and a heightmap
file, if a terrain run names one) and write only inside the run's output folder.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from datetime import datetime
from itertools import count
from pathlib import Path
from typing import Any

from ._meta import PROJECT_NAME, __version__
from .environments import ENVIRONMENTS
from .inspection import inspect_mesh as _inspect_mesh
from .output import _json_default
from .simulation import Simulation

EXPECTED_ERRORS = (FileNotFoundError, ValueError, TypeError, ImportError, OSError)


def _jsonable(data: Any) -> Any:
    return json.loads(json.dumps(data, default=_json_default))


def _existing_file(path: str) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise FileNotFoundError(f"Mesh file not found: {resolved} (relative paths start at {Path.cwd()})")
    return resolved


def _new_run_dir(model: Path, env: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for n in count(1):
        suffix = "" if n == 1 else f"-{n}"
        candidate = Path(f"{PROJECT_NAME}_output") / f"{model.stem}-{env}-{stamp}{suffix}"
        try:
            candidate.mkdir(parents=True)
        except FileExistsError:
            continue
        return candidate
    raise AssertionError("unreachable")


def inspect_mesh(path: str, scale: float | None = None) -> dict[str, Any]:
    """Check a mesh file before simulating it. Use an absolute path.

    Returns its size under each unit interpretation, the likely units and a
    suggested scale, and whether it is watertight, concave or flat-bottomed.
    meshsim works in meters, so act on the units before calling run_simulation.
    """
    return _inspect_mesh(_existing_file(path), scale=scale)


def list_environments() -> dict[str, Any]:
    """List the simulation environments, with each parameter's default value and meaning."""
    return _jsonable(
        {
            name: {
                "description": cls.description,
                "params": {key: {"default": spec.default, "help": spec.help} for key, spec in cls.params.items()},
            }
            for name, cls in sorted(ENVIRONMENTS.items())
        }
    )


def run_simulation(
    path: str,
    env: str = "flat",
    env_params: dict[str, Any] | None = None,
    duration: float | None = None,
    scale: float | None = None,
    density: float | None = None,
    mass: float | None = None,
    friction: float | None = None,
    restitution: float | None = None,
    orientation: list[float] | None = None,
    velocity: list[float] | None = None,
    timestep: float | None = None,
    render: bool = False,
    out_dir: str | None = None,
) -> dict[str, Any]:
    """Simulate a mesh as a rigid body in an environment and save the results. Use absolute paths.

    Units are SI: scale converts mesh units to meters (0.001 for a millimeter
    STL), density is kg/m^3, mass is kg (overrides density), duration and
    timestep are seconds, orientation is roll, pitch, yaw in degrees, and
    velocity is m/s. Results go to out_dir, or a new folder under
    ./meshsim_output/. Returns the metrics and the paths of the files written.
    """
    model = _existing_file(path)
    sim = Simulation(
        model,
        env=env,
        env_params=env_params,
        duration=duration,
        scale=scale,
        density=density,
        mass=mass,
        friction=friction,
        restitution=restitution,
        initial_orientation=orientation,
        initial_velocity=velocity,
        timestep=timestep,
        render=render,
    )
    result = sim.run()
    out = Path(out_dir).expanduser() if out_dir else _new_run_dir(model, sim.environment.name)
    paths = result.save(out)
    return _jsonable(result.report()) | {
        "output_dir": str(out),
        "files": {kind: str(file) for kind, file in paths.items()},
    }


def build_server():
    """Create the MCP server with meshsim's tools registered."""
    try:
        from mcp.server.mcpserver import MCPServer
        from mcp.server.mcpserver.exceptions import ToolError
    except ImportError as exc:
        raise ImportError("The MCP server needs the 'mcp' extra: pip install 'meshsim[mcp]'") from exc

    def tool_errors(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        # The SDK hides the text of unexpected exceptions, and these messages are what the caller needs.
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            try:
                return fn(*args, **kwargs)
            except EXPECTED_ERRORS as exc:
                raise ToolError(str(exc)) from exc

        return wrapper

    server = MCPServer(PROJECT_NAME, version=__version__)
    for fn in (inspect_mesh, list_environments, run_simulation):
        server.add_tool(tool_errors(fn))
    return server


def serve() -> None:
    """Run the server over stdio until the client disconnects."""
    build_server().run("stdio")
