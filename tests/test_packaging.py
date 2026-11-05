"""Checks on the release setup that would otherwise only fail during a real release."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _release_workflow():
    return yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())


def test_release_workflow_runs_only_on_published_releases():
    workflow = _release_workflow()
    # YAML 1.1 reads the bare key `on` as the boolean True.
    assert workflow[True] == {"release": {"types": ["published"]}}


def test_publish_uses_trusted_publishing_without_tokens():
    workflow = _release_workflow()
    publish = workflow["jobs"]["publish"]
    assert publish["needs"] == "build"
    assert publish["permissions"] == {"id-token": "write"}
    assert publish["environment"]["name"] == "pypi"

    step = next(s for s in publish["steps"] if "gh-action-pypi-publish" in s.get("uses", ""))
    assert "password" not in step.get("with", {})
    assert "secrets." not in (ROOT / ".github/workflows/release.yml").read_text()

    # Only the publish job can request an identity token.
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"]["build"]


def test_readme_links_work_on_pypi():
    # The README is the PyPI project page, which can't resolve repo-relative paths.
    readme = (ROOT / "README.md").read_text()
    relative = re.findall(r"\]\((?!https?://|#)([^)]+)\)", readme)
    assert relative == []
