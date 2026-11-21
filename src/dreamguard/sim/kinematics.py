"""Forward kinematics of the simulated YAM arms for DreamGuard workspace / separation checks."""

from __future__ import annotations

import threading
from collections.abc import Sequence

import mujoco

from .scene import ARM_PREFIX, build_model


class SimKinematics:
    """``forward_kinematics(arm, joints) -> (x, y, z)`` of the arm's ``grasp_site`` in metres.

    Positions are in the shared world frame, so both arms can be compared for separation.
    Uses its own ``MjData``, so it never disturbs a running simulation.
    """

    def __init__(self, model: mujoco.MjModel | None = None) -> None:
        self.model = model or build_model()
        self._data = mujoco.MjData(self.model)
        self._lock = threading.Lock()
        self._qpos = {
            arm: [self.model.joint(f"{prefix}joint{j + 1}").qposadr[0] for j in range(6)]
            for arm, prefix in ARM_PREFIX.items()
        }
        self._site = {arm: f"{prefix}grasp_site" for arm, prefix in ARM_PREFIX.items()}

    def __call__(self, arm: str, joints: Sequence[float]) -> tuple[float, float, float]:
        if arm not in self._qpos:
            raise ValueError(f"Unknown arm: {arm}")
        if len(joints) != len(self._qpos[arm]):
            raise ValueError(f"Expected {len(self._qpos[arm])} joint values for {arm} arm")
        with self._lock:
            for qadr, value in zip(self._qpos[arm], joints):
                self._data.qpos[qadr] = value
            mujoco.mj_kinematics(self.model, self._data)
            x, y, z = self._data.site(self._site[arm]).xpos
        return (float(x), float(y), float(z))
