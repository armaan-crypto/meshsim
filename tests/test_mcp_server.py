import asyncio
import json
import math
import sys

import pytest

from meshsim.cli import main
from meshsim.mcp_server import inspect_mesh, list_environments, run_simulation
from meshsim.samples import make_cube


def test_run_simulation_matches_free_fall(tmp_path, cube_stl):
    height = 1.0
    out = tmp_path / "run"
    result = run_simulation(
        str(cube_stl), env="drop", env_params={"height": height}, restitution=0.0, duration=1.0, out_dir=str(out)
    )
    assert result["metrics"]["peak_impact_velocity_m_s"] == pytest.approx(math.sqrt(2 * 9.81 * height), rel=0.02)
    assert result["output_dir"] == str(out)
    assert (out / "plot.png").is_file()
    assert result["files"]["plot"] == str(out / "plot.png")
    assert "render" not in result["files"]
    json.dumps(result)  # MCP results must be plain JSON


def test_run_simulation_render_returns_animation_path(tmp_path, cube_stl):
    result = run_simulation(str(cube_stl), duration=0.1, render=True, out_dir=str(tmp_path))
    assert result["files"]["render"] == str(tmp_path / "render.gif")
    assert (tmp_path / "render.gif").is_file()


def test_run_simulation_default_folder_is_new_for_each_run(tmp_path, monkeypatch, cube_stl):
    monkeypatch.chdir(tmp_path)
    first = run_simulation(str(cube_stl), duration=0.05)
    second = run_simulation(str(cube_stl), duration=0.05)
    assert first["output_dir"] != second["output_dir"]
    for result in (first, second):
        assert result["output_dir"].startswith("meshsim_output/cube-flat-")
        assert (tmp_path / result["files"]["metrics"]).is_file()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"restitution": 2.0}, "restitution must be between 0 and 1"),
        ({"env": "moon"}, "Unknown environment 'moon'"),
        ({"env": "ramp", "env_params": {"tilt": 3}}, "Unknown parameter"),
    ],
)
def test_run_simulation_rejects_bad_parameters(tmp_path, cube_stl, kwargs, message):
    out = tmp_path / "run"
    with pytest.raises(ValueError, match=message):
        run_simulation(str(cube_stl), out_dir=str(out), **kwargs)
    assert not out.exists()


def test_tools_refuse_missing_files(tmp_path):
    missing = str(tmp_path / "nope.stl")
    with pytest.raises(FileNotFoundError, match="Mesh file not found"):
        run_simulation(missing)
    with pytest.raises(FileNotFoundError, match="Mesh file not found"):
        inspect_mesh(missing)


def test_inspect_mesh_flags_millimeter_cube(tmp_path):
    path = tmp_path / "mm_cube.stl"
    make_cube(100.0).export(path)
    info = inspect_mesh(str(path))
    assert info["likely_units"] == "mm"
    assert info["suggested_scale"] == 0.001
    assert info["watertight"] is True
    assert "extents_at_scale_m" not in info
    assert inspect_mesh(str(path), scale=0.001)["extents_at_scale_m"] == pytest.approx([0.1, 0.1, 0.1])


def test_inspect_mesh_rejects_bad_scale(cube_stl):
    with pytest.raises(ValueError, match="scale must be > 0"):
        inspect_mesh(str(cube_stl), scale=0)


def test_list_environments_matches_registry():
    envs = list_environments()
    assert set(envs) == {"flat", "ramp", "drop", "terrain"}
    assert "height" in envs["drop"]["params"]
    assert "default" in envs["drop"]["params"]["height"]
    json.dumps(envs)


def test_cli_explains_missing_extra(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "mcp.server.mcpserver", None)
    assert main(["mcp"]) == 2
    assert "meshsim[mcp]" in capsys.readouterr().err


def test_server_over_stdio(tmp_path, cube_stl):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def session_results():
        params = StdioServerParameters(command=sys.executable, args=["-m", "meshsim", "mcp"], cwd=str(tmp_path))
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            good = await session.call_tool(
                "run_simulation",
                {"path": str(cube_stl), "env": "drop", "env_params": {"height": 0.5}, "duration": 0.6,
                 "restitution": 0.0, "out_dir": str(tmp_path / "run")},
            )
            bad = await session.call_tool("run_simulation", {"path": str(cube_stl), "restitution": 2.0})
            return tools, good, bad

    tools, good, bad = asyncio.run(asyncio.wait_for(session_results(), timeout=60))
    assert {tool.name for tool in tools.tools} == {"inspect_mesh", "list_environments", "run_simulation"}
    run_tool = next(tool for tool in tools.tools if tool.name == "run_simulation")
    assert "restitution" in run_tool.input_schema["properties"]

    assert not good.is_error
    metrics = json.loads(good.content[0].text)["metrics"]
    assert metrics["peak_impact_velocity_m_s"] == pytest.approx(math.sqrt(2 * 9.81 * 0.5), rel=0.02)

    assert bad.is_error
    assert "restitution must be between 0 and 1" in bad.content[0].text
