"""Flat ground: the object starts resting on a horizontal plane."""

from __future__ import annotations

import numpy as np

from .base import IDENTITY, Environment, Param, SpawnFrame, add_ground, require_non_negative


class FlatGround(Environment):
    name = "flat"
    description = "Horizontal ground plane at z=0. The object starts just above it."
    params = {
        "friction": Param(1.0, "Ground friction (multiplied with the object's friction)"),
        "restitution": Param(1.0, "Ground restitution (multiplied with the object's restitution)"),
        "clearance": Param(0.001, "Starting gap between the object's lowest point and the ground, m"),
    }

    def validate(self) -> None:
        require_non_negative(self, "friction", "restitution", "clearance")

    def build(self, client) -> None:
        add_ground(client, self.friction, self.restitution)

    def spawn_frame(self, client) -> SpawnFrame:
        return SpawnFrame(origin=np.zeros(3), orientation=IDENTITY.copy(), gap=self.clearance)
