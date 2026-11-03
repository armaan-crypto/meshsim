"""Slide a plastic wedge down a ramp at two friction levels.

Run from the repository root:
    python examples/wedge_ramp.py
Outputs go to examples/output/wedge_ramp_*/.
The same run from the CLI, using the YAML file next to this script:
    meshsim run examples/output/wedge.stl --config examples/wedge_ramp.yaml
"""

from pathlib import Path

from meshsim import Simulation
from meshsim.samples import make_wedge

HERE = Path(__file__).parent

mesh_path = HERE / "output" / "wedge.stl"
mesh_path.parent.mkdir(parents=True, exist_ok=True)
make_wedge(length=0.3, width=0.2, height=0.15).export(mesh_path)

for friction in (0.15, 0.6):
    result = Simulation(
        mesh_path,
        config=HERE / "wedge_ramp.yaml",
        friction=friction,  # keyword overrides beat the YAML file
    ).run()
    out = result.save(HERE / "output" / f"wedge_ramp_mu{friction}")
    m = result.metrics
    settle = f"{m['settle_time_s']:.2f} s" if m["settled"] else "did not settle"
    print(
        f"friction {friction}: traveled {m['total_distance_m']:.2f} m, "
        f"max speed {m['max_speed_m_s']:.2f} m/s, settled: {settle} -> {out['metrics'].parent}"
    )
