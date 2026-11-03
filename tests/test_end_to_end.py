import csv
import json
import math

import pytest

from meshsim import Simulation
from meshsim.cli import main


@pytest.mark.parametrize("height", [0.5, 1.0, 2.0])
def test_free_fall_matches_analytic(cube, height):
    """Time to first contact should be sqrt(2h/g) and impact speed sqrt(2gh)."""
    g = 9.81
    result = Simulation(cube, env="drop", env_params={"height": height}, gravity=g, restitution=0.0,
                        duration=math.sqrt(2 * height / g) + 0.5).run()
    m = result.metrics
    assert m["first_contact_time_s"] == pytest.approx(math.sqrt(2 * height / g), rel=0.02)
    assert m["peak_impact_velocity_m_s"] == pytest.approx(math.sqrt(2 * g * height), rel=0.02)


def test_lower_gravity_falls_slower(cube):
    result = Simulation(cube, env="drop", env_params={"height": 1.0}, gravity=1.62, duration=1.5).run()
    assert result.metrics["first_contact_time_s"] == pytest.approx(math.sqrt(2 / 1.62), rel=0.02)


def test_save_writes_all_outputs(tmp_path, cube):
    result = Simulation(cube, env="drop", duration=1.0, render=True, render_fps=5, render_size=(64, 48)).run()
    assert len(result.frames) == 6  # t = 0, 0.2, ..., 1.0
    paths = result.save(tmp_path)
    assert set(paths) == {"trajectory", "metrics", "plot", "render"}
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0

    report = json.loads(paths["metrics"].read_text())
    for key in ["peak_acceleration_m_s2", "peak_impact_velocity_m_s", "settle_time_s", "final_position_m",
                "final_orientation_quat_xyzw", "total_distance_m"]:
        assert key in report["metrics"]
    assert report["model"]["mass_kg"] == pytest.approx(8.0)
    assert report["environment"]["name"] == "drop"

    with paths["trajectory"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 241  # 1 s at 240 Hz plus the initial state
    assert float(rows[0]["z"]) == pytest.approx(1.1, abs=1e-6)

    from PIL import Image

    with Image.open(paths["render"]) as gif:
        assert gif.size == (64, 48)
        assert gif.n_frames >= 2  # Pillow merges identical frames once the cube is at rest


def test_mp4_render(tmp_path, cube):
    pytest.importorskip("imageio_ffmpeg")
    result = Simulation(cube, env="drop", duration=0.5, render=True, render_format="mp4", render_fps=10,
                        render_size=(64, 48)).run()
    paths = result.save(tmp_path)
    assert paths["render"].suffix == ".mp4" and paths["render"].stat().st_size > 0


def test_cli_run(tmp_path, cube_stl, capsys):
    out = tmp_path / "out"
    code = main(["run", str(cube_stl), "--env", "ramp", "-p", "angle=30", "--friction", "0.2",
                 "--duration", "1", "--out", str(out)])
    assert code == 0
    assert (out / "trajectory.csv").exists()
    report = json.loads((out / "metrics.json").read_text())
    assert report["environment"]["params"]["angle"] == 30
    assert report["config"]["friction"] == 0.2
    assert "peak acceleration" in capsys.readouterr().out


def test_cli_with_yaml_and_flag_override(tmp_path, cube_stl):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("env: drop\nenv_params:\n  height: 0.3\nduration: 0.5\ndensity: 500\n")
    out = tmp_path / "out"
    assert main(["run", str(cube_stl), "-c", str(cfg), "--density", "2000", "--out", str(out), "--no-plot"]) == 0
    report = json.loads((out / "metrics.json").read_text())
    assert report["model"]["density_kg_m3"] == pytest.approx(2000)
    assert report["environment"]["params"]["height"] == 0.3
    assert not (out / "plot.png").exists()


def test_cli_reports_errors(tmp_path, capsys):
    assert main(["run", str(tmp_path / "missing.stl")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_envs(capsys):
    assert main(["envs"]) == 0
    out = capsys.readouterr().out
    for name in ["flat", "ramp", "drop", "terrain"]:
        assert f"{name}:" in out
