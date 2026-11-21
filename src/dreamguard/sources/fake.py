"""Offline stand-in for ``dream.DreamClient``: scripted action chunks with fault injection.

It mirrors the SDK's inference surface (``policy``, ``set_observation``, ``get_action``,
``reset_episode``, ``close``, context manager) and never touches the network, so it costs nothing.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Mapping, Sequence
from typing import Any, Self

JOINTS_PER_ARM = 6
HOME = (0.0, 1.047, 1.047, 0.0, 0.0, 0.0)

# (right arm joints, left arm joints, gripper 0 closed .. 1 open). The left arm mirrors the
# right arm's base and wrist rotations so both reach toward the objects in front of them.
WAYPOINTS: tuple[tuple[Sequence[float], Sequence[float], float], ...] = (
    (HOME, HOME, 1.0),
    ((0.15, 1.6, 1.2, 0.0, 0.2, 0.0), (-0.15, 1.6, 1.2, 0.0, -0.2, 0.0), 1.0),
    ((0.15, 1.6, 1.2, 0.0, 0.2, 0.0), (-0.15, 1.6, 1.2, 0.0, -0.2, 0.0), 0.0),
    ((0.3, 1.3, 1.1, 0.0, 0.3, 0.0), (-0.3, 1.3, 1.1, 0.0, -0.3, 0.0), 0.0),
    (HOME, HOME, 1.0),
)

# Fault catalogue: each produces one specific kind of unsafe chunk on the next get_action().
FAULTS: dict[str, str] = {
    "joint_limit": "Right wrist joint 4 ramps past its +1.571 rad limit",
    "big_step": "Right arm's first row jumps 0.6 rad away from the measured pose",
    "velocity": "Right joint 1 jumps 0.25 rad between two rows (5 rad/s at 20 Hz)",
    "nan": "A NaN joint target in the right arm chunk",
    "gripper": "Right gripper command of 1.4 (valid range 0..1)",
    "missing_arm": "The left arm chunk (q_l_chunk) is missing",
    "mismatched_lengths": "The left arm chunk has half as many rows as the right arm chunk",
    "workspace": "Right gripper is driven below the table surface",
    "separation": "Both grippers converge on the same point between the arms",
}
FAULT_TARGETS = {
    "workspace": ((0.0, 2.0, 0.95, 0.0, 0.0, 0.0), None),
    "separation": ((0.6, 1.6, 1.2, 0.0, 0.0, 0.0), (-0.6, 1.6, 1.2, 0.0, 0.0, 0.0)),
}


class FakeClientError(RuntimeError):
    """Misuse of the fake client, mirroring the SDK's config / observation errors."""


def _ramp(start: Sequence[float], target: Sequence[float], rows: int, max_step: float):
    """Rows moving each joint from ``start`` toward ``target`` by at most ``max_step`` per row."""
    current = list(start)
    out = []
    for _ in range(rows):
        current = [c + max(-max_step, min(max_step, t - c)) for c, t in zip(current, target)]
        out.append(list(current))
    return out


class FakeDreamClient:
    def __init__(
        self,
        *,
        rows: int = 50,
        action_hz: float = 20.0,
        joint_speed_rad_s: float = 1.0,
        gripper_speed_per_s: float = 2.0,
        waypoints: Sequence[tuple[Sequence[float], Sequence[float], float]] = WAYPOINTS,
    ) -> None:
        if rows < 1 or action_hz <= 0 or joint_speed_rad_s <= 0:
            raise ValueError("rows, action_hz and joint_speed_rad_s must be positive")
        self.rows = rows
        self.action_hz = action_hz
        self.max_step = joint_speed_rad_s / action_hz
        self.gripper_step = gripper_speed_per_s / action_hz
        self.waypoints = tuple(waypoints)
        self.waypoint_index = 0
        self.calls = 0
        self._config: Mapping[str, Any] | None = None
        self._observation: Mapping[str, Any] | None = None
        self._pending_faults: list[str] = []
        self.last_faults: tuple[str, ...] = ()  # faults applied to the most recent chunk
        self._lock = threading.Lock()

    # --- SDK inference surface -----------------------------------------------------------

    def policy(self, config: Mapping[str, Any]) -> None:
        self._config = dict(config)
        self.reset_episode()

    def set_observation(
        self, frames: Mapping[str, Any], observation: Mapping[str, Any], *, timestamp=None
    ) -> None:
        if self._config is None:
            raise FakeClientError("policy() must be called before set_observation()")
        self._observation = observation

    def get_action(self, *, commanded: Mapping[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if self._config is None:
                raise FakeClientError("policy() must be called before get_action()")
            if self._observation is None:
                raise FakeClientError("get_action() called before any set_observation()")
            self.calls += 1
            action = self._scripted_chunk()
            faults, self._pending_faults = self._pending_faults, []
            self.last_faults = tuple(faults)
        for fault in faults:
            self._apply_fault(fault, action)
        return action

    def reset_episode(self) -> None:
        with self._lock:
            self._observation = None
            self.waypoint_index = 0
            self._pending_faults = []

    def close(self) -> None:
        self._config = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- Fault injection -----------------------------------------------------------------

    def inject(self, fault: str) -> None:
        """Make the next chunk unsafe in the named way (see ``FAULTS``)."""
        if fault not in FAULTS:
            raise ValueError(f"Unknown fault {fault!r}; expected one of {', '.join(FAULTS)}")
        with self._lock:
            self._pending_faults.append(fault)

    # --- Chunk generation ----------------------------------------------------------------

    def _measured(self, arm: str) -> tuple[list[float], float]:
        observation = self._observation or {}
        joints = observation.get(f"state.{arm}_arm", HOME)
        gripper = observation.get(f"state.{arm}_gripper", [1.0])
        joints = joints.tolist() if hasattr(joints, "tolist") else list(joints)
        gripper = gripper.tolist() if hasattr(gripper, "tolist") else list(gripper)
        return [float(v) for v in joints], float(gripper[0])

    def _scripted_chunk(self) -> dict[str, Any]:
        right_target, left_target, gripper_target = self.waypoints[self.waypoint_index]
        chunk: dict[str, Any] = {}
        reached = True
        for arm, target in (("right", right_target), ("left", left_target)):
            joints, gripper = self._measured(arm)
            rows = _ramp(joints, target, self.rows, self.max_step)
            grippers = _ramp([gripper], [gripper_target], self.rows, self.gripper_step)
            chunk[f"q_{arm[0]}_chunk"] = [r + g for r, g in zip(rows, grippers)]
            reached &= max(abs(a - b) for a, b in zip(joints, target)) < 0.02
            reached &= abs(gripper - gripper_target) < 0.15
        if reached:
            self.waypoint_index = (self.waypoint_index + 1) % len(self.waypoints)
        return chunk

    def _apply_fault(self, fault: str, action: dict[str, Any]) -> None:
        right = action["q_r_chunk"]
        if fault == "joint_limit":
            ramp = _ramp([right[0][3]], [1.9], len(right), self.max_step)
            for row, (value,) in zip(right, ramp):
                row[3] = value
        elif fault == "big_step":
            for row in right:
                row[0] += 0.6
        elif fault == "velocity":
            for row in right[len(right) // 3 :]:
                row[0] += 0.25
        elif fault == "nan":
            right[min(5, len(right) - 1)][2] = math.nan
        elif fault == "gripper":
            for row in right:
                row[JOINTS_PER_ARM] = 1.4
        elif fault == "missing_arm":
            del action["q_l_chunk"]
        elif fault == "mismatched_lengths":
            action["q_l_chunk"] = action["q_l_chunk"][: max(1, len(right) // 2)]
        elif fault in FAULT_TARGETS:
            right_target, left_target = FAULT_TARGETS[fault]
            for key, target in (("q_r_chunk", right_target), ("q_l_chunk", left_target)):
                if target is None:
                    continue
                rows = action[key]
                ramp = _ramp(rows[0][:JOINTS_PER_ARM], target, len(rows), self.max_step)
                for row, joints in zip(rows, ramp):
                    row[:JOINTS_PER_ARM] = joints
