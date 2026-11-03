import pytest

from meshsim import SimConfig


def test_defaults():
    cfg = SimConfig()
    assert cfg.env == "flat"
    assert cfg.timestep == pytest.approx(1 / 240)
    assert cfg.mass is None


def test_yaml_loading(tmp_path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        "env: ramp\n"
        "env_params:\n  angle: 30\n"
        "density: 2700\nfriction: 0.3\nrestitution: 0.1\ngravity: 1.62\ntimestep: 0.002\n"
        "initial_orientation: [0, 0, 45]\n"
    )
    cfg = SimConfig.from_yaml(path)
    assert cfg.env == "ramp"
    assert cfg.env_params == {"angle": 30}
    assert cfg.density == 2700
    assert cfg.gravity == pytest.approx(1.62)
    assert cfg.initial_orientation == (0.0, 0.0, 45.0)


def test_empty_yaml_gives_defaults(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("")
    assert SimConfig.from_yaml(path) == SimConfig()


def test_unknown_key_rejected():
    with pytest.raises(ValueError, match="Unknown config key"):
        SimConfig.from_dict({"frictoin": 0.3})


@pytest.mark.parametrize(
    "values",
    [{"duration": 0}, {"timestep": -1}, {"restitution": 1.5}, {"mass": -2}, {"friction": -0.1},
     {"render_format": "avi"}, {"initial_velocity": [1, 2]}],
)
def test_invalid_values_rejected(values):
    with pytest.raises(ValueError):
        SimConfig.from_dict(values)


def test_overrides_take_precedence_and_merge_env_params():
    cfg = SimConfig(env="ramp", env_params={"angle": 30, "friction": 0.5}, density=500)
    new = cfg.with_overrides(density=800, mass=None, env_params={"angle": 10})
    assert new.density == 800
    assert new.env_params == {"angle": 10, "friction": 0.5}


def test_changing_env_drops_old_env_params():
    cfg = SimConfig(env="ramp", env_params={"angle": 30})
    assert cfg.with_overrides(env="drop").env_params == {}


def test_load_accepts_dict_and_none():
    assert SimConfig.load(None) == SimConfig()
    assert SimConfig.load({"duration": 2}).duration == 2
