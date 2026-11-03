"""Drop a 20 cm aluminium cube from 1.5 m and compare impact speed with theory.

The cube is tilted a few degrees so it lands on an edge first, as real drops do.
(A perfectly flat face-down landing with restitution > 0 is a known weak spot of
Bullet's contact solver; see "Known limitations" in the README.)

Run from the repository root:
    python examples/cube_drop.py
Outputs go to examples/output/cube_drop/.
"""

import math
from pathlib import Path

from meshsim import Simulation
from meshsim.samples import make_cube

HERE = Path(__file__).parent
HEIGHT = 1.5

mesh_path = HERE / "output" / "cube.stl"
mesh_path.parent.mkdir(parents=True, exist_ok=True)
make_cube(0.2).export(mesh_path)

sim = Simulation(
    mesh_path,
    env="drop",
    env_params={"height": HEIGHT},
    density=2700,  # aluminium
    restitution=0.4,
    initial_orientation=(4, 3, 0),  # roll, pitch, yaw in degrees
    duration=3.0,
    render=True,
)
result = sim.run()
paths = result.save(HERE / "output" / "cube_drop")

m = result.metrics
print(f"mass:                 {sim.body.mass:.2f} kg")
print(f"first contact:        {m['first_contact_time_s']:.3f} s (theory {math.sqrt(2 * HEIGHT / 9.81):.3f} s)")
print(f"peak impact velocity: {m['peak_impact_velocity_m_s']:.3f} m/s (theory {math.sqrt(2 * 9.81 * HEIGHT):.3f} m/s)")
print(f"bounces:              {m['impact_count']}")
print(f"settle time:          {m['settle_time_s']} s")
for kind, path in paths.items():
    print(f"wrote {kind}: {path}")
