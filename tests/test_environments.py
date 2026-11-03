import math

import numpy as np
import pytest
import trimesh

from meshsim import Simulation
from meshsim._bullet import new_client
from meshsim.environments import ENVIRONMENTS, DropTest, FlatGround, Ramp, Terrain, load_heightmap, make_environment


def test_registry_has_builtins():
    assert {"flat", "ramp", "drop", "terrain"} <= set(ENVIRONMENTS)


def test_unknown_environment():
    with pytest.raises(ValueError, match="Unknown environment"):
        make_environment("moon")


def test_unknown_parameter():
    with pytest.raises(ValueError, match="Unknown parameter"):
        Ramp(slope=10)


@pytest.mark.parametrize(
    "factory",
    [lambda: Ramp(angle=95), lambda: Ramp(start_distance=10, length=5), lambda: DropTest(height=0),
     lambda: FlatGround(friction=-1), lambda: Terrain(), lambda: Terrain(heightmap=np.zeros((3, 3)), mesh="x.stl")],
)
def test_invalid_parameters(factory):
    with pytest.raises(ValueError):
        factory()


def test_flat_ground_object_stays_at_rest(cube):
    result = Simulation(cube, env="flat", duration=1.0).run()
    m = result.metrics
    assert m["settled"]
    assert m["final_position_m"][2] == pytest.approx(0.1, abs=3e-3)
    assert m["total_distance_m"] < 5e-3


def test_drop_starts_at_height(cube):
    result = Simulation(cube, env="drop", env_params={"height": 0.5}, duration=0.5).run()
    # Lowest point 0.5 m above the floor, so the center of a 0.2 m cube starts at 0.6 m.
    assert result.trajectory["z"][0] == pytest.approx(0.6, abs=1e-6)
    assert result.metrics["impact_count"] >= 1


def test_ramp_low_friction_slides_with_expected_acceleration(cube):
    angle, mu = 30.0, 0.2
    result = Simulation(cube, env="ramp", env_params={"angle": angle}, friction=mu, restitution=0.0,
                        duration=0.6).run()
    traj = result.trajectory
    i = int(np.searchsorted(traj["time"], 0.5))
    expected = 9.81 * (math.sin(math.radians(angle)) - mu * math.cos(math.radians(angle))) * traj["time"][i]
    assert traj["speed"][i] == pytest.approx(expected, rel=0.05)
    # Moving down the slope means moving toward +X.
    assert traj["vx"][i] > 0


def test_ramp_high_friction_holds_object(cube):
    result = Simulation(cube, env="ramp", env_params={"angle": 20}, friction=1.0, duration=1.0).run()
    assert result.metrics["total_distance_m"] < 0.01


def test_ramp_slides_onto_ground(cube):
    result = Simulation(cube, env="ramp", env_params={"angle": 35, "start_distance": 1.0}, friction=0.2,
                        duration=4.0).run()
    final_x, _, final_z = result.metrics["final_position_m"]
    assert final_x > 0  # past the bottom edge at x=0
    assert final_z == pytest.approx(0.1, abs=5e-3)  # resting on the ground


def test_heightmap_surface_height_matches_grid():
    cell = 0.5
    xs = (np.arange(13) - 6) * cell
    ys = (np.arange(9) - 4) * cell
    heights = 0.5 * xs[None, :] + 0.1 * ys[:, None]  # rows -> Y, columns -> X
    terrain = Terrain(heightmap=heights, cell_size=cell)
    client = new_client()
    try:
        terrain.build(client)
        for x, y in [(0, 0), (1, 0), (0, 1), (-2, 1.5)]:
            assert terrain.surface_height(client, x, y) == pytest.approx(0.5 * x + 0.1 * y, abs=1e-5)
    finally:
        client.disconnect()


def test_heightmap_file_formats(tmp_path):
    grid = np.arange(12, dtype=float).reshape(3, 4)
    np.save(tmp_path / "h.npy", grid)
    np.savetxt(tmp_path / "h.csv", grid, delimiter=",")
    assert np.array_equal(load_heightmap(tmp_path / "h.npy"), grid)
    assert np.array_equal(load_heightmap(tmp_path / "h.csv"), grid)


def test_heightmap_image_is_normalized(tmp_path):
    from PIL import Image

    pixels = np.array([[0, 255], [128, 255]], dtype=np.uint8)
    Image.fromarray(pixels).save(tmp_path / "h.png")
    data = load_heightmap(tmp_path / "h.png")
    assert data.min() == 0.0 and data.max() == 1.0
    assert data[0, 0] == pytest.approx(128 / 255)  # image rows are flipped so row 0 is the bottom edge


def test_object_comes_to_rest_on_heightmap(cube):
    heights = np.full((20, 20), 0.75)
    result = Simulation(cube, env=Terrain(heightmap=heights, cell_size=0.5), duration=1.5).run()
    assert result.metrics["settled"]
    assert result.metrics["final_position_m"][2] == pytest.approx(0.75 + 0.1, abs=5e-3)


def test_terrain_mesh(tmp_path, cube):
    # A 4 m x 4 m slab whose top surface is at z=0.3.
    slab = trimesh.creation.box(extents=(4, 4, 0.2))
    slab.apply_translation([10, 10, 0.2])  # off-center on purpose; center=True moves it under the origin
    path = tmp_path / "terrain.stl"
    slab.export(path)
    result = Simulation(cube, env="terrain", env_params={"mesh": str(path)}, duration=1.5).run()
    assert result.metrics["final_position_m"][2] == pytest.approx(0.3 + 0.1, abs=5e-3)


def test_custom_environment_instance(cube):
    env = DropTest(height=0.25)
    sim = Simulation(cube, env=env, duration=0.3)
    assert sim.environment is env
    assert sim.config.env == "drop"
