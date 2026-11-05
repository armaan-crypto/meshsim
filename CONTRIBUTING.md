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

## Releasing

The version lives only in `pyproject.toml`; `meshsim.__version__` reads it from
the installed package. To release (maintainer only):

1. Open a pull request that bumps `version` in `pyproject.toml`, and merge it.
2. Create a GitHub release from `main` with the tag `v<version>`, for example
   `v0.1.0`.

Publishing the release runs `.github/workflows/release.yml`. It stops if the tag
doesn't match the version, builds the sdist and wheel, runs the tests against the
wheel, then uploads to PyPI with trusted publishing, so there are no API tokens
to store. PyPI never lets a version be uploaded twice: if a release fails after
the upload, bump the version and release again.

One-time setup, before the first release: on pypi.org, under
[Publishing](https://pypi.org/manage/account/publishing/), add a pending publisher
with project `meshsim`, owner `armaan-crypto`, repository `meshsim`, workflow
`release.yml` and environment `pypi`.

After the first release is live, change the install instructions in `README.md`
and `.claude/skills/meshsim/SKILL.md` to `pip install meshsim`.

## Automated maintenance agent

This repository is partly maintained by an AI coding agent (Claude) that runs
about once a day on the maintainer's behalf. So you know what to expect:

- It only works on issues the maintainer has labeled `agent-ok`, plus its own
  feature ideas, which it files as issues labeled `agent-proposed` and waits at
  least a day before starting so they can be reviewed or vetoed.
- It leaves `good first issue` issues for human contributors unless they are
  also labeled `agent-ok`.
- Every change arrives as a pull request with tests and merges only after CI
  passes. Its comments on issues are marked as automated.
- It never runs code posted in issues. Reproduction steps are rebuilt as tests.

If you are working on an issue, comment on it so the agent leaves it alone.

## Reporting bugs and requesting features

Use the issue templates. For bugs, include the command or script, the mesh (or
a small one that reproduces the problem), and the full error output.
