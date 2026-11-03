"""The Simulation class: the Python API that the CLI wraps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from ._bullet import new_client, p
from ._meta import PROJECT_NAME, __version__
from ._rotation import quat_conjugate, quat_from_euler_deg, quat_multiply, quat_to_matrix
from .config import SimConfig
from .environments import Environment, make_environment
from .mesh import BodyProperties, compute_body_properties, load_mesh
from .metrics import compute_metrics
from .output import write_animation, write_json, write_plot, write_trajectory_csv

OBJECT_RGBA = [0.90, 0.45, 0.15, 1.0]
CONTACT_TOLERANCE = 1e-3  # m; a contact point closer than this counts as touching
CAMERA_DIRECTION = np.array([0.3, -1.0, 0.3])  # target-to-eye: from the -Y side, slightly ahead and above


@dataclass
class SimulationResult:
    """Everything a run produces. Call ``save()`` to write it to disk."""

    trajectory: dict[str, np.ndarray]
    metrics: dict[str, Any]
    config: SimConfig
    model: dict[str, Any]
    environment: dict[str, Any]
    title: str
    frames: list[np.ndarray] | None = field(default=None, repr=False)

    def report(self) -> dict[str, Any]:
        """The full metrics document written to metrics.json."""
        return {
            "tool": PROJECT_NAME,
            "version": __version__,
            "model": self.model,
            "environment": self.environment,
            "config": self.config.to_dict() | {"env_params": self.environment["params"]},
            "metrics": self.metrics,
        }

    def save(self, output_dir: str | Path | None = None) -> dict[str, Path]:
        """Write trajectory.csv, metrics.json, plot.png and (if rendered) the animation."""
        out = Path(output_dir or self.config.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = {
            "trajectory": write_trajectory_csv(self.trajectory, out / "trajectory.csv"),
            "metrics": write_json(self.report(), out / "metrics.json"),
        }
        if self.config.plot:
            paths["plot"] = write_plot(self.trajectory, self.metrics, self.title, out / "plot.png")
        if self.frames:
            paths["render"] = write_animation(
                self.frames, self.config.render_fps, out / f"render.{self.config.render_format}"
            )
        return paths


class Simulation:
    """Drop a mesh into an environment and simulate it with PyBullet.

    Example::

        from meshsim import Simulation
        result = Simulation("part.stl", env="ramp", duration=5, env_params={"angle": 25}).run()
        print(result.metrics["settle_time_s"])
        result.save("out/")

    ``config`` may be a SimConfig, a dict, or a path to a YAML file. Keyword
    overrides take precedence over it. ``env`` may also be an Environment instance.
    """

    def __init__(
        self,
        model: str | Path | trimesh.Trimesh,
        config: SimConfig | dict | str | Path | None = None,
        **overrides: Any,
    ) -> None:
        env_override = overrides.pop("env", None)
        if isinstance(env_override, Environment):
            self.config = SimConfig.load(config).with_overrides(env=env_override.name, **overrides)
            self.environment = env_override
        else:
            self.config = SimConfig.load(config).with_overrides(env=env_override, **overrides)
            self.environment = make_environment(self.config.env, self.config.env_params)

        self.model_name = model.metadata.get("file_name", "mesh") if isinstance(model, trimesh.Trimesh) else str(model)
        self.mesh = load_mesh(model, scale=self.config.scale)
        self.body: BodyProperties = compute_body_properties(
            self.mesh, density=self.config.density, mass=self.config.mass
        )

    def run(self) -> SimulationResult:
        cfg = self.config
        client = new_client()
        try:
            client.setGravity(0, 0, -cfg.gravity)
            client.setTimeStep(cfg.timestep)
            self.environment.build(client)
            body_id = self._create_body(client)
            traj, body_quats = self._step(client, body_id)
            frames = self._render(client, body_id, traj, body_quats) if cfg.render else None
        finally:
            client.disconnect()

        metrics = compute_metrics(traj, cfg.settle_speed, cfg.settle_angular_speed, cfg.settle_window)
        return SimulationResult(
            trajectory=traj,
            metrics=metrics,
            config=cfg,
            model={"source": self.model_name, "scale": cfg.scale, **self.body.summary()},
            environment=self.environment.describe(),
            title=f"{Path(self.model_name).name} in '{self.environment.name}'",
            frames=frames,
        )

    def _spawn_pose(self, client) -> tuple[np.ndarray, np.ndarray]:
        """Body position (center of mass) and body orientation at t=0."""
        frame = self.environment.spawn_frame(client)
        mesh_quat = quat_multiply(frame.orientation, quat_from_euler_deg(self.config.initial_orientation))
        body_quat = quat_multiply(mesh_quat, self.body.body_to_mesh)
        world_vertices = self.body.hull_vertices_body @ quat_to_matrix(body_quat).T
        frame_normal = quat_to_matrix(frame.orientation)[:, 2]
        lowest = -np.min(world_vertices @ frame_normal)
        position = np.asarray(frame.origin, dtype=float) + frame_normal * (lowest + frame.gap)
        return position, body_quat

    def _create_body(self, client) -> int:
        cfg = self.config
        collision = client.createCollisionShape(p.GEOM_MESH, vertices=self.body.hull_vertices_body.tolist())
        visual = client.createVisualShape(
            p.GEOM_MESH,
            vertices=self.body.vertices_body.tolist(),
            indices=self.body.faces.flatten().tolist(),
            rgbaColor=OBJECT_RGBA,
        )
        position, orientation = self._spawn_pose(client)
        body_id = client.createMultiBody(
            baseMass=self.body.mass,
            baseCollisionShapeIndex=collision,
            baseVisualShapeIndex=visual,
            basePosition=position.tolist(),
            baseOrientation=orientation.tolist(),
        )
        client.changeDynamics(
            body_id,
            -1,
            lateralFriction=cfg.friction,
            restitution=cfg.restitution,
            linearDamping=cfg.linear_damping,
            angularDamping=cfg.angular_damping,
            localInertiaDiagonal=self.body.inertia_diagonal.tolist(),
        )
        client.resetBaseVelocity(body_id, linearVelocity=list(cfg.initial_velocity))
        return body_id

    def _step(self, client, body_id: int) -> tuple[dict[str, np.ndarray], np.ndarray]:
        cfg = self.config
        n_steps = int(round(cfg.duration / cfg.timestep))
        n = n_steps + 1
        pos = np.zeros((n, 3))
        body_quats = np.zeros((n, 4))
        vel = np.zeros((n, 3))
        ang = np.zeros((n, 3))
        contact = np.zeros(n, dtype=int)

        def record(i: int) -> None:
            position, orientation = client.getBasePositionAndOrientation(body_id)
            linear, angular = client.getBaseVelocity(body_id)
            pos[i], body_quats[i], vel[i], ang[i] = position, orientation, linear, angular
            points = client.getContactPoints(bodyA=body_id)
            contact[i] = int(any(pt[8] <= CONTACT_TOLERANCE for pt in points))

        record(0)
        for i in range(1, n):
            client.stepSimulation()
            record(i)

        accel = np.zeros_like(vel)
        accel[1:] = np.diff(vel, axis=0) / cfg.timestep
        accel[0] = accel[1] if n > 1 else 0.0
        # Report the orientation of the original mesh axes, not the internal principal-axis frame.
        mesh_quats = quat_multiply(body_quats, quat_conjugate(self.body.body_to_mesh))
        traj = {
            "time": np.arange(n) * cfg.timestep,
            "x": pos[:, 0], "y": pos[:, 1], "z": pos[:, 2],
            "qx": mesh_quats[:, 0], "qy": mesh_quats[:, 1], "qz": mesh_quats[:, 2], "qw": mesh_quats[:, 3],
            "vx": vel[:, 0], "vy": vel[:, 1], "vz": vel[:, 2],
            "wx": ang[:, 0], "wy": ang[:, 1], "wz": ang[:, 2],
            "speed": np.linalg.norm(vel, axis=1),
            "angular_speed": np.linalg.norm(ang, axis=1),
            "ax": accel[:, 0], "ay": accel[:, 1], "az": accel[:, 2],
            "accel": np.linalg.norm(accel, axis=1),
            "contact": contact,
        }
        return traj, body_quats

    def _render(self, client, body_id: int, traj: dict[str, np.ndarray], body_quats: np.ndarray) -> list[np.ndarray]:
        """Replay the recorded poses and capture frames with PyBullet's software renderer."""
        cfg = self.config
        width, height = cfg.render_size
        times = traj["time"]
        frame_times = np.arange(0.0, times[-1] + 1e-9, 1.0 / cfg.render_fps)
        indices = np.searchsorted(times, frame_times).clip(0, len(times) - 1)

        path = np.column_stack([traj["x"], traj["y"], traj["z"]])
        lo, hi = path.min(axis=0), path.max(axis=0)
        target = (lo + hi) / 2
        size = float(np.max(self.body.extents))
        # Fit the whole path in the horizontal field of view (about 62 degrees at 4:3 with a 50 degree vertical FOV).
        distance = max(1.1 * float(np.max(hi - lo)) + 4 * size, 4 * size, 0.5)
        eye = target + distance * CAMERA_DIRECTION / np.linalg.norm(CAMERA_DIRECTION)
        view = client.computeViewMatrix(
            cameraEyePosition=eye.tolist(), cameraTargetPosition=target.tolist(), cameraUpVector=[0, 0, 1]
        )
        projection = client.computeProjectionMatrixFOV(fov=50, aspect=width / height, nearVal=0.01, farVal=1000)

        frames = []
        for i in indices:
            client.resetBasePositionAndOrientation(body_id, path[i].tolist(), body_quats[i].tolist())
            image = client.getCameraImage(
                width, height, viewMatrix=view, projectionMatrix=projection, renderer=p.ER_TINY_RENDERER,
                shadow=1, lightDirection=[0.5, -0.6, 1.0],
            )
            rgba = np.asarray(image[2], dtype=np.uint8).reshape(height, width, 4)
            frames.append(rgba[:, :, :3].copy())
        return frames
