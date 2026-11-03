"""Project identity.

The user-facing name (CLI program name, default output folder, plot titles,
metrics header) is read from ``PROJECT_NAME``. See "Renaming the project" in
CONTRIBUTING.md for the other places that have to change with it.
"""

from importlib.metadata import PackageNotFoundError, version

PROJECT_NAME = "meshsim"

try:
    __version__ = version(PROJECT_NAME)
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0+unknown"
