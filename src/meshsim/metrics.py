"""Scalar metrics computed from a recorded trajectory."""

from __future__ import annotations

from typing import Any

import numpy as np

from ._rotation import quat_to_euler_deg

STANDARD_GRAVITY = 9.80665


def compute_metrics(
    traj: dict[str, np.ndarray],
    settle_speed: float,
    settle_angular_speed: float,
    settle_window: float,
) -> dict[str, Any]:
    """Compute summary metrics.

    - peak_acceleration: largest magnitude of the center-of-mass acceleration
      (finite difference of velocity). During impacts this depends on the
      timestep and contact model, so treat it as indicative, not exact.
    - impacts: steps where the object goes from no contact to contact while
      moving faster than ``settle_speed``. Impact velocity is the speed on the
      last step before contact.
    - settle time: start of the final stretch where linear and angular speed
      stay under their thresholds; it must last at least ``settle_window``.
    """
    t = traj["time"]
    pos = np.column_stack([traj["x"], traj["y"], traj["z"]])
    speed = traj["speed"]
    ang_speed = traj["angular_speed"]
    accel = traj["accel"]
    contact = traj["contact"].astype(bool)

    peak_idx = int(np.argmax(accel))
    starts = np.flatnonzero(~contact[:-1] & contact[1:]) + 1
    impact_speeds = [float(speed[i - 1]) for i in starts if speed[i - 1] > settle_speed]
    impact_times = [float(t[i]) for i in starts if speed[i - 1] > settle_speed]
    first_contact = float(t[np.argmax(contact)]) if contact.any() else None

    moving = (speed > settle_speed) | (ang_speed > settle_angular_speed)
    if not moving.any():
        settle_time: float | None = 0.0
    else:
        last_moving = int(np.flatnonzero(moving)[-1])
        if last_moving == len(t) - 1 or t[-1] - t[last_moving + 1] < settle_window:
            settle_time = None
        else:
            settle_time = float(t[last_moving + 1])

    steps = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    final_q = np.array([traj["qx"][-1], traj["qy"][-1], traj["qz"][-1], traj["qw"][-1]])

    return {
        "duration_s": float(t[-1]),
        "peak_acceleration_m_s2": float(accel[peak_idx]),
        "peak_acceleration_g": float(accel[peak_idx] / STANDARD_GRAVITY),
        "peak_acceleration_time_s": float(t[peak_idx]),
        "max_speed_m_s": float(speed.max()),
        "first_contact_time_s": first_contact,
        "impact_count": len(impact_speeds),
        "impact_times_s": impact_times,
        "peak_impact_velocity_m_s": max(impact_speeds) if impact_speeds else None,
        "settled": settle_time is not None,
        "settle_time_s": settle_time,
        "total_distance_m": float(steps.sum()),
        "net_displacement_m": float(np.linalg.norm(pos[-1] - pos[0])),
        "initial_position_m": pos[0].tolist(),
        "final_position_m": pos[-1].tolist(),
        "final_orientation_quat_xyzw": final_q.tolist(),
        "final_orientation_euler_deg": quat_to_euler_deg(final_q).tolist(),
    }
