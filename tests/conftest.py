import pytest

from meshsim.samples import make_cube, make_wedge


@pytest.fixture
def cube():
    return make_cube(0.2)


@pytest.fixture
def wedge():
    return make_wedge()


@pytest.fixture
def cube_stl(tmp_path, cube):
    path = tmp_path / "cube.stl"
    cube.export(path)
    return path
