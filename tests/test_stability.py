import json
import math

import numpy as np
import pytest
import trimesh

from meshsim import Simulation, stable_poses, tip_angles
from meshsim.cli import main
from meshsim.samples import make_cube


def tall_box(width=0.1, depth=0.1, height=0.3):
    box = trimesh.creation.box(extents=(width, depth, height))
    box.apply_translation((0, 0, height / 2))
    return box


def test_box_tip_angle_matches_closed_form():
    result = tip_angles(tall_box(0.1, 0.2, 0.4))
    assert result.stable
    assert result.com_height_m == pytest.approx(0.2)
    assert result.support_area_m2 == pytest.approx(0.02)
    # The narrow side (half width 0.05) tips first, along +X or -X.
    assert result.min_tip_angle_deg == pytest.approx(math.degrees(math.atan(0.05 / 0.2)), abs=0.5)
    assert result.min_tip_azimuth_deg % 180 == pytest.approx(0, abs=1e-6)
    angles = {d["azimuth_deg"]: d["tip_angle_deg"] for d in result.directions}
    assert angles[0] == pytest.approx(math.degrees(math.atan(0.05 / 0.2)), abs=0.5)
    assert angles[90] == pytest.approx(math.degrees(math.atan(0.1 / 0.2)), abs=0.5)
    # Toward a corner the reach is limited by the first edge the ray meets: 0.05 / cos 45.
    assert angles[45] == pytest.approx(math.degrees(math.atan(0.05 * math.sqrt(2) / 0.2)), abs=0.5)


def test_minimum_is_exact_when_samples_miss_the_nearest_edge():
    # The nearest edges face +Y and -Y, and the single sample direction (+X) never points at them.
    result = tip_angles(tall_box(0.4, 0.1, 0.4), directions=1)
    assert result.directions[0]["tip_angle_deg"] == pytest.approx(math.degrees(math.atan(0.2 / 0.2)))
    assert result.min_tip_angle_deg == pytest.approx(math.degrees(math.atan(0.05 / 0.2)))


def test_cylinder_tips_at_the_same_angle_in_every_direction():
    cylinder = trimesh.creation.cylinder(radius=0.05, height=0.3, sections=64)
    result = tip_angles(cylinder, directions=16)
    expected = math.degrees(math.atan(0.05 / 0.15))
    for direction in result.directions:
        assert direction["tip_angle_deg"] == pytest.approx(expected, abs=0.5)


def test_added_mass_above_the_center_lowers_the_angle():
    box = tall_box()  # 3 kg at 1000 kg/m^3, center of mass 0.15 m up
    plain = tip_angles(box)
    loaded = tip_angles(box, add_mass=3.0, add_mass_at=(0, 0, 0.45))
    assert loaded.total_mass_kg == pytest.approx(6.0)
    assert loaded.com_height_m == pytest.approx(0.3)
    assert loaded.min_tip_angle_deg == pytest.approx(math.degrees(math.atan(0.05 / 0.3)), abs=0.5)
    assert loaded.min_tip_angle_deg < plain.min_tip_angle_deg


def test_off_center_mass_sets_the_weakest_direction():
    # 3 kg box plus 3 kg at x=0.04 puts the combined center of mass at x=0.02, height 0.15.
    result = tip_angles(tall_box(), add_mass=3.0, add_mass_at=(0.04, 0, 0.15))
    assert result.min_tip_azimuth_deg == pytest.approx(0, abs=1e-6)
    assert result.min_tip_angle_deg == pytest.approx(math.degrees(math.atan(0.03 / 0.15)), abs=0.5)


def test_mass_outside_the_base_cannot_rest():
    result = tip_angles(tall_box(), add_mass=30.0, add_mass_at=(0.2, 0, 0.1))
    assert not result.stable
    assert result.min_tip_angle_deg == 0.0
    assert all(d["tip_angle_deg"] == 0.0 for d in result.directions)


def test_balancing_on_an_edge_is_not_stable():
    result = tip_angles(make_cube(0.2), orientation=(45, 0, 0))
    assert not result.stable
    assert result.support_area_m2 == 0.0


def test_orientation_poses_the_part_first():
    # Lying on its side, the 0.3 m box has its center of mass at 0.05 m above a wide base.
    result = tip_angles(tall_box(), orientation=(90, 0, 0))
    assert result.com_height_m == pytest.approx(0.05)
    assert result.min_tip_angle_deg == pytest.approx(45.0, abs=0.5)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"directions": 0},
        {"add_mass": 1.0},
        {"add_mass_at": (0, 0, 0)},
        {"add_mass": -1.0, "add_mass_at": (0, 0, 0)},
        {"add_mass": 1.0, "add_mass_at": (0, 0, -1)},
        {"com": (0, 0, -1)},
    ],
)
def test_bad_inputs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        tip_angles(tall_box(), **kwargs)


def test_stable_poses_rest_on_the_largest_faces_first():
    pytest.importorskip("networkx")
    poses = stable_poses(tall_box())
    assert sum(pose["probability"] for pose in poses) == pytest.approx(1.0, abs=0.01)
    likeliest = tip_angles(tall_box(), orientation=poses[0]["orientation_deg"])
    assert likeliest.stable
    assert likeliest.com_height_m == pytest.approx(0.05)  # lying on a long side


def test_stable_poses_explains_the_missing_extra(monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    with pytest.raises(ImportError, match=r"meshsim\[poses\]"):
        stable_poses(tall_box())


@pytest.mark.parametrize("angle,tips", [(16.0, False), (21.0, True)])
def test_ramp_agrees_with_static_tip_angle(angle, tips):
    box = tall_box()
    predicted = tip_angles(box).min_tip_angle_deg
    assert predicted == pytest.approx(18.43, abs=0.1)
    result = Simulation(box, env="ramp", env_params={"angle": angle}, friction=2.0, restitution=0.0, duration=2.5).run()
    assert (result.metrics["max_tilt_deg"] > 45.0) is tips
    assert result.metrics["tipped_over"] is tips
    if not tips:
        assert result.metrics["max_tilt_deg"] < 5.0


def test_hard_push_tips_a_tall_box_and_gentle_push_does_not():
    box = tall_box(0.05, 0.05, 0.3)
    hard = Simulation(box, env="flat", friction=1.0, restitution=0.0, initial_velocity=(2.0, 0, 0), duration=3.0).run()
    gentle = Simulation(box, env="flat", friction=1.0, restitution=0.0, initial_velocity=(0.1, 0, 0),
                        duration=3.0).run()
    assert hard.metrics["tipped_over"] is True
    assert hard.metrics["max_tilt_deg"] > 45.0
    assert gentle.metrics["tipped_over"] is False
    assert gentle.metrics["max_tilt_deg"] < 45.0


def test_tip_threshold_setting_changes_the_flag():
    box = tall_box(0.05, 0.05, 0.3)
    result = Simulation(box, env="flat", friction=1.0, restitution=0.0, initial_velocity=(2.0, 0, 0), duration=3.0,
                        tip_threshold=179.0).run()
    assert result.metrics["max_tilt_deg"] > 45.0
    assert result.metrics["tipped_over"] is False


def test_tip_threshold_is_validated():
    with pytest.raises(ValueError, match="tip_threshold"):
        Simulation(tall_box(), tip_threshold=0)


def test_spin_about_the_vertical_is_not_tilt():
    from meshsim.metrics import _tilt_from_start_deg

    half = math.radians(90) / 2
    quats = np.array([[0, 0, 0, 1.0], [0, 0, math.sin(half), math.cos(half)], [math.sin(half), 0, 0, math.cos(half)]])
    tilt = _tilt_from_start_deg(quats)
    assert tilt[0] == pytest.approx(0.0)
    assert tilt[1] == pytest.approx(0.0)
    assert tilt[2] == pytest.approx(90.0)


def test_cli_stability(tmp_path, capsys):
    path = tmp_path / "box.stl"
    tall_box().export(path)
    out = tmp_path / "stability.json"
    code = main(["stability", str(path), "--add-mass", "3", "--at", "0", "0", "0.45", "--json", str(out)])
    assert code == 0
    printed = capsys.readouterr().out
    assert "tip angle" in printed
    report = json.loads(out.read_text())
    assert report["stability"]["com_height_m"] == pytest.approx(0.3)
    assert report["stability"]["min_tip_angle_deg"] == pytest.approx(math.degrees(math.atan(0.05 / 0.3)), abs=0.5)


def test_cli_stability_scale_applies_to_the_mesh(tmp_path, capsys):
    path = tmp_path / "box_mm.stl"
    tall_box(100, 100, 300).export(path)
    assert main(["stability", str(path), "--scale", "0.001"]) == 0
    assert "COM height          0.15 m" in capsys.readouterr().out


def test_cli_stability_warns_when_it_cannot_rest(tmp_path, capsys):
    path = tmp_path / "cube.stl"
    make_cube(0.2).export(path)
    assert main(["stability", str(path), "--orientation", "45", "0", "0"]) == 0
    assert "cannot rest" in capsys.readouterr().out


def test_cli_stability_list_poses(tmp_path, capsys):
    pytest.importorskip("networkx")
    path = tmp_path / "box.stl"
    tall_box().export(path)
    assert main(["stability", str(path), "--list-poses"]) == 0
    assert "--orientation" in capsys.readouterr().out


def test_cli_stability_requires_at_with_add_mass(tmp_path, capsys):
    path = tmp_path / "box.stl"
    tall_box().export(path)
    assert main(["stability", str(path), "--add-mass", "1"]) == 2
    assert "add_mass" in capsys.readouterr().err


def test_cli_run_prints_tilt(tmp_path, cube_stl, capsys):
    assert main(["run", str(cube_stl), "--duration", "0.5", "--no-plot", "--out", str(tmp_path / "out")]) == 0
    printed = capsys.readouterr().out
    assert "max tilt" in printed
    report = json.loads((tmp_path / "out" / "metrics.json").read_text())
    assert report["metrics"]["tipped_over"] is False
    assert report["metrics"]["max_tilt_deg"] < 1.0
