# Typical material values

Starting points for `--density`, `--friction` and `--restitution` when the
user names a material but not its properties. Real values vary with grade,
infill, surface finish, moisture and temperature, so always tell the user which
values you assumed. If they have measured values, use those.

## Density (kg/m³)

| Material | Density | Notes |
|---|---|---|
| PLA | 1240 | Solid. For 3D prints, multiply by the effective fill, e.g. 20% infill with walls is often 0.4–0.6 of solid |
| ABS | 1040 | |
| PETG | 1270 | |
| TPU (flexible) | 1200 | meshsim still treats it as rigid |
| Nylon (PA12) | 1010 | |
| Polycarbonate | 1200 | |
| Acrylic (PMMA) | 1180 | |
| HDPE | 950 | |
| Rubber (natural) | 1100 | |
| Pine / softwood | 500 | |
| Oak / hardwood | 750 | |
| Aluminium | 2700 | |
| Titanium | 4430 | |
| Steel | 7850 | |
| Stainless steel | 8000 | |
| Brass | 8500 | |
| Glass | 2500 | |
| Concrete | 2400 | |

For hollow or shelled parts, prefer `--mass` with the real (weighed or CAD) mass;
density times the closed volume overestimates mass for anything not solid.

## Friction coefficient (dry, approximate)

meshsim uses a single Coulomb coefficient per contact, so pick a value between
the usual static and kinetic figures, closer to static when the question is
"does it start to slide".

| Pair | μ |
|---|---|
| PTFE on most surfaces | 0.05–0.1 |
| Ice on ice or steel | 0.02–0.1 |
| Smooth plastic on plastic | 0.2–0.4 |
| Plastic on wood | 0.3–0.5 |
| Wood on wood | 0.25–0.5 |
| Metal on metal (dry) | 0.4–0.8 |
| Aluminium on steel | 0.45–0.6 |
| Plastic or metal on concrete | 0.5–0.7 |
| Rubber on concrete or asphalt (dry) | 0.6–0.9 |
| Rubber on wet surfaces | 0.25–0.5 |

## Restitution (approximate)

How much bounce: 0 = no bounce, 1 = perfectly elastic.

| Situation | e |
|---|---|
| Clay, foam, soft padding | 0–0.1 |
| Wood on concrete | 0.3–0.5 |
| Hard plastic part on a hard floor | 0.3–0.5 |
| Steel on steel | 0.5–0.7 |
| Rubber ball on a hard floor | 0.7–0.9 |

The defaults (friction 0.5, restitution 0.2) are a reasonable generic hard-part
setting when the user gives nothing to go on.
