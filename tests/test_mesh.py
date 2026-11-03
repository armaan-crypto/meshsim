import numpy as np
import pytest
import trimesh

from meshsim import compute_body_properties, load_mesh


@pytest.mark.parametrize("suffix", [".stl", ".obj", ".ply"])
def test_load_formats(tmp_path, cube, suffix):
    path = tmp_path / f"cube{suffix}"
    cube.export(path)
    mesh = load_mesh(path)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(0.008, rel=1e-6)


def test_scale_converts_millimeters(tmp_path):
    path = tmp_path / "mm_cube.stl"
    trimesh.creation.box(extents=(200, 200, 200)).export(path)
    mesh = load_mesh(path, scale=0.001)
    assert np.allclose(mesh.extents, [0.2, 0.2, 0.2])


def test_cleanup_merges_duplicates_and_drops_degenerate_faces(cube):
    # Unmerged copy of the cube with one degenerate (zero-area) face appended.
    vertices = cube.vertices[cube.faces].reshape(-1, 3)
    faces = np.arange(len(vertices)).reshape(-1, 3)
    faces = np.vstack([faces, [[0, 0, 1]]])
    messy = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh = load_mesh(messy)
    assert len(mesh.vertices) == 8
    assert len(mesh.faces) == 12
    assert mesh.is_watertight


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_mesh(tmp_path / "nope.stl")


def test_unsupported_format(tmp_path):
    path = tmp_path / "model.xyz"
    path.write_text("1 2 3\n")
    with pytest.raises(ValueError, match="Unsupported"):
        load_mesh(path)


def test_mass_properties_from_density(cube):
    body = compute_body_properties(cube, density=2700)
    assert body.mass == pytest.approx(0.008 * 2700)
    # Solid cube: I = m * a^2 / 6 about each axis.
    assert np.allclose(body.inertia_diagonal, body.mass * 0.2**2 / 6)
    assert np.allclose(body.vertices_body.mean(axis=0), 0, atol=1e-9)


def test_mass_overrides_density(wedge):
    body = compute_body_properties(wedge, density=1000, mass=3.0)
    assert body.mass == pytest.approx(3.0)
    assert body.density == pytest.approx(3.0 / wedge.volume)


def test_wedge_center_of_mass(wedge):
    body = compute_body_properties(wedge)
    # Right-triangle prism: centroid at 2/3 of the length (toward the tall end) and 1/3 of the height.
    assert np.allclose(body.center_of_mass, [0.2, 0.1, 0.05])


def test_open_mesh_falls_back_to_convex_hull(cube):
    open_mesh = cube.copy()
    open_mesh.update_faces(np.arange(len(open_mesh.faces)) != 0)
    with pytest.warns(UserWarning, match="not watertight"):
        body = compute_body_properties(load_mesh(open_mesh))
    assert body.watertight is False
    assert body.volume == pytest.approx(0.008)
