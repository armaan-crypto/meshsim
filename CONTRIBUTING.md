# Contributing to meshsim

Thanks for your interest. meshsim is early, so bug reports, small fixes, tests
and new environments are all useful.

## Development setup

```bash
git clone https://github.com/armaan-crypto/meshsim && cd meshsim
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,video]"
```

On Apple Silicon Macs, PyBullet is compiled from source; if the build fails in
`zutil.c`, run `CFLAGS="-Dfdopen=fdopen" pip install pybullet` first.

## Checks

CI runs these on Python 3.10, 3.11 and 3.12. Run them before opening a pull request:

```bash
ruff check .
pytest
```

## Guidelines

- Keep changes focused; one topic per pull request.
- Add or update tests for behavior you change. For physics features, prefer a
  test against a closed-form result (see `tests/test_end_to_end.py`).
- Do not add placeholder features. If something is not implemented, it should
  raise a clear error or not exist yet.
- Keep dependencies minimal. Optional features go behind an extra in
  `pyproject.toml`.
- Units are SI throughout; say so in docstrings when a value has units.

## Adding an environment

1. Create `src/meshsim/environments/<name>.py` with a subclass of `Environment`.
   Set `name`, `description` and `params`, and implement `build(client)` (create
   static bodies) and `spawn_frame(client)` (where the part starts).
2. Register it in `src/meshsim/environments/__init__.py`.
3. Add tests in `tests/test_environments.py`.

External code can also call `meshsim.register_environment(MyEnv)` without
changing meshsim.

## Renaming the project

The user-facing name (CLI program name, default output folder, plot titles,
metrics header) comes from `PROJECT_NAME` in `src/meshsim/_meta.py`. A full
rename also needs:

- `name` and the `[project.scripts]` entry in `pyproject.toml`
- the package directory `src/meshsim/` and the `meshsim` imports in tests and examples
- links in `README.md`, this file and `CODE_OF_CONDUCT.md`

## Reporting bugs and requesting features

Use the issue templates. For bugs, include the command or script, the mesh (or
a small one that reproduces the problem), and the full error output.
