"""Writers for simulation outputs: CSV, JSON, plot and animation."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np

from ._meta import PROJECT_NAME

TRAJECTORY_COLUMNS = [
    "time", "x", "y", "z", "qx", "qy", "qz", "qw",
    "vx", "vy", "vz", "wx", "wy", "wz",
    "speed", "angular_speed", "ax", "ay", "az", "accel", "contact",
]


def write_trajectory_csv(traj: dict[str, np.ndarray], path: Path) -> Path:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(TRAJECTORY_COLUMNS)
        columns = [traj[name] for name in TRAJECTORY_COLUMNS]
        for row in zip(*columns, strict=True):
            writer.writerow([f"{v:.9g}" if isinstance(v, (float, np.floating)) else int(v) for v in row])
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(data: dict[str, Any], path: Path) -> Path:
    with path.open("w") as fh:
        json.dump(data, fh, indent=2, default=_json_default)
        fh.write("\n")
    return path


def write_plot(traj: dict[str, np.ndarray], metrics: dict[str, Any], title: str, path: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = traj["time"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), constrained_layout=True)
    fig.suptitle(f"{PROJECT_NAME}: {title}")

    ax = axes[0, 0]
    for key, color in (("x", "#1f77b4"), ("y", "#2ca02c"), ("z", "#d62728")):
        ax.plot(t, traj[key], label=key, color=color)
    ax.set(title="Center of mass position", xlabel="time (s)", ylabel="m")
    ax.legend(loc="best")

    ax = axes[0, 1]
    ax.plot(t, traj["speed"], color="#1f77b4", label="speed")
    if metrics["settle_time_s"] is not None:
        ax.axvline(metrics["settle_time_s"], color="gray", ls="--", label=f"settled @ {metrics['settle_time_s']:.2f} s")
    for i, t_imp in enumerate(metrics["impact_times_s"]):
        ax.axvline(t_imp, color="#d62728", alpha=0.35, lw=1, label="impact" if i == 0 else None)
    ax.set(title="Speed", xlabel="time (s)", ylabel="m/s")
    ax.legend(loc="best")

    ax = axes[1, 0]
    accel_g = traj["accel"] / 9.80665
    ax.plot(t, accel_g, color="#9467bd")
    ax.plot(metrics["peak_acceleration_time_s"], metrics["peak_acceleration_g"], "o", color="#d62728",
            label=f"peak {metrics['peak_acceleration_g']:.1f} g")
    ax.set(title="Acceleration magnitude", xlabel="time (s)", ylabel="g")
    ax.legend(loc="best")

    ax = axes[1, 1]
    horizontal = np.hypot(traj["x"] - traj["x"][0], traj["y"] - traj["y"][0])
    ax.plot(horizontal, traj["z"], color="#ff7f0e")
    ax.plot(horizontal[0], traj["z"][0], "o", color="#2ca02c", label="start")
    ax.plot(horizontal[-1], traj["z"][-1], "s", color="#d62728", label="end")
    ax.set(title="Path (side view)", xlabel="horizontal distance from start (m)", ylabel="z (m)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="best")

    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def write_animation(frames: list[np.ndarray], fps: int, path: Path) -> Path:
    """Write frames as a GIF (Pillow) or MP4 (imageio + imageio-ffmpeg)."""
    if not frames:
        raise ValueError("No frames to write")
    suffix = path.suffix.lower()
    if suffix == ".gif":
        from PIL import Image

        images = [Image.fromarray(frame) for frame in frames]
        images[0].save(
            path, save_all=True, append_images=images[1:], duration=round(1000 / fps), loop=0, optimize=False
        )
    elif suffix == ".mp4":
        if importlib.util.find_spec("imageio") is None or importlib.util.find_spec("imageio_ffmpeg") is None:
            raise ImportError("MP4 output needs imageio and imageio-ffmpeg: pip install 'meshsim[video]'")
        import imageio.v2 as imageio

        with imageio.get_writer(path, fps=fps, codec="libx264", macro_block_size=8) as writer:
            for frame in frames:
                writer.append_data(frame)
    else:
        raise ValueError(f"Unsupported animation format '{suffix}' (use .gif or .mp4)")
    return path
