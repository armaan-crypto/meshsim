---
name: meshsim
description: Run physics tests on 3D models (STL, OBJ, PLY, STEP) with the meshsim rigid-body simulator and explain the results. Use this whenever someone wants to know how a physical part or CAD design behaves under gravity and contact - drop tests ("what speed does it hit the floor at", "does it bounce"), slopes and ramps ("will it slide on a 20 degree incline", "what friction keeps it in place"), whether something tips over or where it comes to rest, landing on terrain or a scanned surface, or comparing designs and materials by impact speed, settle time or distance traveled. Use it even if the user doesn't mention meshsim or simulation, as long as they have (or can export) a mesh and a physical "what happens if" question.
---

# meshsim: physics tests for 3D designs

meshsim drops a mesh into a simple world (flat ground, ramp, drop height, or
terrain), simulates it as a rigid body with PyBullet, and writes metrics, a
trajectory, a plot and optionally an animation. Your job is to turn a person's
physical question into the right run, check the inputs so the numbers mean
something, and explain the answer in plain language with honest caveats.

## 1. Find or install meshsim

Try, in order: `meshsim --version`, then `python -m meshsim --version` using a
project virtualenv if one exists (for example `.venv/bin/python` in the meshsim
repo). Use whichever works for every later command; the `meshsim` command and
`python -m meshsim` take the same arguments.

If neither works, tell the user you are installing it, then:

```bash
pip install "git+https://github.com/armaan-crypto/meshsim"
```

PyBullet often compiles from source (Apple Silicon Macs, Linux on Python 3.12),
which takes a few minutes. On macOS, if the build fails in `zutil.c`, run
`CFLAGS="-Dfdopen=fdopen" pip install pybullet` first. Add `[video]` to the
install for MP4 output.

## 2. Inspect the mesh before simulating

Run the bundled helper with the same Python that has meshsim:

```bash
python <this-skill-dir>/scripts/inspect_mesh.py path/to/part.stl
```

It prints the raw size with each unit interpretation, the likely units and a
suggested `--scale`, and flags open meshes, concave shapes and flat bottoms.
Act on what it reports, because each of these silently changes the answer:

- **Units.** meshsim works in meters. A part that is really 80 mm but simulated
  as 80 m gives meaningless numbers. CAD exports are usually millimeters
  (`--scale 0.001`). If the helper says "ambiguous", ask the user, or state the
  assumption you made prominently.
- **Open mesh.** Mass and inertia fall back to the convex hull. Mention it.
- **Concave.** The part collides as its convex hull, so slots, hollows and
  channels act as if filled. Say so when the question depends on that shape
  (for example something resting inside a U-channel, or a hook catching).
- **Flat bottom + drop test.** A perfectly flat face-down landing with
  restitution > 0 produces spurious spin in Bullet. Add a small tilt
  (`--orientation 4 3 0`) and tell the user you did, since real drops are
  rarely perfectly flat anyway.

## 3. Map the question to a run

| Question | Environment | Key settings |
|---|---|---|
| Impact speed, bounce, landing from a height | `drop` | `-p height=H` (gap between lowest point and floor, m) |
| Does it slide or stay on a slope? How far does it go? | `ramp` | `-p angle=DEG`, `--friction MU` |
| Does it tip over, where does it rest, is it stable? | `flat` | `--orientation R P Y` to start it tilted; `--velocity` to push it |
| Behavior on uneven ground or a scan | `terrain` | `-p heightmap=FILE` or `-p mesh=FILE`, `-p cell_size=`, `-p height_scale=` |

Run `meshsim envs` to see every environment parameter and its default.

Physical inputs: pick density, friction and restitution from the material and
surface the user describes. `references/materials.md` has typical values. Tell
the user which values you assumed, because they drive the result. If they give
a mass, use `--mass` (it overrides density).

How friction and restitution combine: Bullet multiplies the part's value by the
surface's value. Surfaces default to 1.0, so by default `--friction` and
`--restitution` are the effective contact values. Only change surface values
(`-p friction=...`) to model two different surfaces on one ramp.

## 4. Run it

Give each run its own output folder so runs don't overwrite each other:

```bash
meshsim run part.stl --scale 0.001 --env drop -p height=1.2 --density 1200 \
  --restitution 0.5 --orientation 4 3 0 --out runs/drop_1p2m
```

Add `--render` when the user would benefit from seeing the motion (GIF by
default). For comparisons or sweeps (several materials, angles or designs), use
the Python API in a short script instead of many CLI calls:

```python
from meshsim import Simulation

for angle in [10, 15, 20, 25, 30]:
    result = Simulation("part.stl", env="ramp", env_params={"angle": angle},
                        friction=0.4, scale=0.001, duration=4).run()
    m = result.metrics
    print(angle, round(m["total_distance_m"], 3), m["settled"])
    result.save(f"runs/ramp_{angle}")
```

A YAML file (`--config test.yaml`) is useful when the user wants a repeatable
test they can rerun. Every CLI flag has a YAML key of the same name (see the
meshsim README).

## 5. Read and check the results

Read `metrics.json` in the output folder. The fields that answer most questions:

| Field | Meaning |
|---|---|
| `peak_impact_velocity_m_s` | Speed just before the hardest impact. `null` if it never hit anything while moving |
| `first_contact_time_s`, `impact_count`, `impact_times_s` | When it first touched, and how many bounces |
| `peak_acceleration_g` | Highest acceleration of the center of mass. During impacts this depends on timestep and contact stiffness: use it to compare designs under identical settings, never as an absolute shock rating |
| `settled`, `settle_time_s` | Whether and when it came to rest (stayed below speed thresholds for `settle_window` s). If `settled` is false, rerun with a longer `--duration` before concluding it never stops |
| `total_distance_m`, `net_displacement_m` | Path length, and straight-line distance from start to finish. Near 0 on a ramp means it held |
| `final_position_m`, `final_orientation_euler_deg` | Where it ended up and how it's rotated (degrees, relative to the mesh's own axes). A large final roll or pitch means it tipped |
| `model.mass_kg` | Check this matches reality. A wrong mass usually means wrong units or density |

Look at `plot.png` with your image-reading tool. It shows position, speed with
impacts marked, acceleration, and the side-view path, and it is the fastest way
to catch a run that went wrong (part fell off the edge of the ramp, never
settled, flew away).

Cross-check against simple physics when you can. It catches setup mistakes and
gives the user confidence:

- Drop from height h: first contact at about √(2h/g), impact speed about √(2gh).
- Ramp at angle θ: a block slides when the effective friction is below tan θ, and
  its speed along the slope grows at g(sin θ − μ cos θ).
- Impact energy: ½ m v², with m from `model.mass_kg`.

If the simulation disagrees noticeably with these, investigate (units, start
orientation, the part rolling instead of sliding) before reporting.

**Check the timestep for thin parts and hard impacts.** Each physics step the
part moves `speed × timestep` (about 2 cm per step at 5 m/s with the default
1/240 s). When that is a sizable fraction of the part's thinnest dimension, the
part sinks into the floor on impact and bounce heights and rebound directions
become unreliable. The signs: the minimum `z` in `trajectory.csv` goes below 0
in a `drop` or `flat` run, or the plot's z curve dips under the floor. Rerun with
`--timestep 0.001` and compare; trust the result once two timesteps agree.
For example, a 12 mm-thick phone case dropped from 1.2 m bounced 0.30 m at
1/240 s but 0.12 m at both 1/1000 s and 1/2000 s. Impact speed was the same at
all three. Peak acceleration always rises as the timestep shrinks, which is
why it is only a relative measure.

## 6. Report back

Lead with the direct answer to their question in one or two sentences, then the
supporting numbers with units, then assumptions and caveats. Keep caveats to the
ones that matter for this run. For example:

> It slides. On a 25° ramp with friction 0.3 (ABS on smooth plastic, assumed)
> the wedge reaches 2.1 m/s and travels 3.2 m before stopping on the floor
> after 2.6 s. Because tan 25° = 0.47 is above 0.3, sliding is expected;
> friction above about 0.47 would hold it.
> Files: runs/wedge_ramp/ (metrics.json, plot.png, trajectory.csv)

Be clear about what meshsim cannot tell them. It treats the part as perfectly
rigid, so it can't say whether something cracks, dents or bends. For "will it
break?" questions, give the impact speed, energy and peak acceleration, explain
that judging damage needs FEA or a physical test, and don't present the
simulation as a certification or standard drop test.

## Limitations to keep in mind

- Rigid bodies only: no deformation, stress, fluids or heat.
- Collision uses the convex hull of the part (mass and inertia use the real
  shape when the mesh is closed).
- One friction coefficient per contact (no separate static and kinetic values).
- Z is up. If a model was exported Y-up it will lie on its side; rotate it with
  `--orientation 90 0 0` and confirm with the user.
- STEP files need the optional `cascadio` package (`pip install "meshsim[step]"`).
  Converting to STL is the more reliable route.
