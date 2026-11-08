"""Inspect a mesh before simulating it with meshsim.

Prints size in the file's raw units with candidate unit interpretations, whether
the mesh is closed, how concave it is, and whether it has a large flat bottom.
Run it with the Python environment that has meshsim installed:

    python inspect_mesh.py part.stl [--json]
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    from meshsim import describe_inspection, inspect_mesh
except ImportError:
    sys.exit("meshsim is missing or too old in this Python environment. See the meshsim skill's install steps.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mesh")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args()
    info = inspect_mesh(args.mesh)
    print(json.dumps(info, indent=2) if args.json else describe_inspection(info))


if __name__ == "__main__":
    main()
