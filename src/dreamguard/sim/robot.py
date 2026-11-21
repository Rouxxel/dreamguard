"""MuJoCo bimanual YAM robot exposing the robot API a Dream-1 control loop needs."""

from __future__ import annotations

import base64
import io
import threading
import time
from collections.abc import Mapping
from typing import Any

import mujoco
import numpy as np
from PIL import Image

from .scene import (
    ARM_PREFIX,
    CAMERA_HEIGHT,
    CAMERA_WIDTH,
    CAMERAS,
    FINGER_OPEN_M,
    HOME_JOINTS,
    build_model,
)

ARMS = ("right", "left")
ACTION_KEYS = {"right": "q_r_chunk", "left": "q_l_chunk"}
JOINTS_PER_ARM = 6
# The finger slide joint stops at 0.0375 m even though its actuator accepts up to 0.041 m.
FINGER_READ_MAX_M = 0.037524


class SimRobot:
    """Two position-controlled YAM arms in MuJoCo.

    - ``joints(arm)`` / ``gripper(arm)``: measured state (float32, radians / 0 closed to 1 open)
    - ``observation(prompt)`` and ``frames()``: the Dream-1 ``set_observation`` inputs
    - ``play(action)``: one chunk row per control tick at ``action_hz``; joint targets and the
      gripper go to the position actuators. Nothing played means the arms hold their targets.

    Physics and rendering are serialized with a lock, so a camera thread can render while a
    control thread plays. Renderers are created per thread (OpenGL contexts are thread-bound).
    """

    def __init__(
        self,
        model: mujoco.MjModel | None = None,
        *,
        action_hz: float = 20.0,
        execution_horizon: int = 30,
        realtime: bool = False,
        jpeg_quality: int = 85,
    ) -> None:
        if action_hz <= 0 or execution_horizon < 1:
            raise ValueError("action_hz must be > 0 and execution_horizon >= 1")
        self.model = model or build_model()
        self.data = mujoco.MjData(self.model)
        self.action_hz = action_hz
        self.execution_horizon = execution_horizon
        self.realtime = realtime
        self.jpeg_quality = jpeg_quality
        self.substeps = max(1, round(1.0 / (action_hz * self.model.opt.timestep)))
        self.rows_played = 0
        self._lock = threading.RLock()
        self._interrupt = threading.Event()
        self._local = threading.local()
        self._renderers: list[mujoco.Renderer] = []

        m = self.model
        self._qpos = {
            arm: [m.joint(f"{ARM_PREFIX[arm]}joint{j + 1}").qposadr[0] for j in range(6)]
            for arm in ARMS
        }
        self._finger_qpos = {
            arm: m.joint(f"{ARM_PREFIX[arm]}left_finger").qposadr[0] for arm in ARMS
        }
        self._mirror_finger_qpos = {
            arm: m.joint(f"{ARM_PREFIX[arm]}right_finger").qposadr[0] for arm in ARMS
        }
        self._joint_ctrl = {
            arm: [m.actuator(f"{ARM_PREFIX[arm]}joint{j + 1}").id for j in range(6)]
            for arm in ARMS
        }
        self._gripper_ctrl = {arm: m.actuator(f"{ARM_PREFIX[arm]}gripper").id for arm in ARMS}
        self.reset()

    # --- State -----------------------------------------------------------------------------

    def reset(self) -> None:
        """Home pose, grippers open, objects back in place."""
        with self._lock:
            mujoco.mj_resetData(self.model, self.data)
            for arm in ARMS:
                for qadr, act, value in zip(self._qpos[arm], self._joint_ctrl[arm], HOME_JOINTS):
                    self.data.qpos[qadr] = value
                    self.data.ctrl[act] = value
                self.data.ctrl[self._gripper_ctrl[arm]] = FINGER_OPEN_M
                # Start with the fingers open (the right finger mirrors the left one).
                self.data.qpos[self._finger_qpos[arm]] = FINGER_READ_MAX_M
                self.data.qpos[self._mirror_finger_qpos[arm]] = -FINGER_READ_MAX_M
            mujoco.mj_forward(self.model, self.data)
            self.rows_played = 0
            self._interrupt.clear()

    def joints(self, arm: str) -> np.ndarray:
        with self._lock:
            return self.data.qpos[self._qpos[arm]].astype(np.float32)

    def gripper(self, arm: str) -> np.ndarray:
        with self._lock:
            opening = self.data.qpos[self._finger_qpos[arm]] / FINGER_READ_MAX_M
        return np.array([np.clip(opening, 0.0, 1.0)], dtype=np.float32)

    def current_joints(self) -> dict[str, np.ndarray]:
        return {arm: self.joints(arm) for arm in ARMS}

    def observation(self, prompt: str = "") -> dict[str, Any]:
        """Dream-1 ``observation``: the ``state.`` arrays (float32) and the prompt."""
        observation: dict[str, Any] = {}
        for arm in ARMS:
            observation[f"state.{arm}_arm"] = self.joints(arm)
            observation[f"state.{arm}_gripper"] = self.gripper(arm)
        observation["prompt"] = prompt
        return observation

    # --- Cameras ---------------------------------------------------------------------------

    def _renderer(self) -> mujoco.Renderer:
        renderer = getattr(self._local, "renderer", None)
        if renderer is None:
            renderer = mujoco.Renderer(self.model, CAMERA_HEIGHT, CAMERA_WIDTH)
            self._local.renderer = renderer
            self._renderers.append(renderer)
        return renderer

    def render(self, role: str) -> np.ndarray:
        """RGB image (176x320x3) from a Dream-1 camera role: overhead, wrist_l, wrist_r."""
        renderer = self._renderer()
        with self._lock:
            renderer.update_scene(self.data, camera=CAMERAS[role])
        return renderer.render()

    def jpeg(self, role: str) -> str:
        """Base64 JPEG without a ``data:`` prefix, as ``set_observation`` expects."""
        buffer = io.BytesIO()
        Image.fromarray(self.render(role)).save(buffer, format="JPEG", quality=self.jpeg_quality)
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def frames(self) -> dict[str, str]:
        """Dream-1 ``frames``: one JPEG per camera window key."""
        return {f"video.{role}": self.jpeg(role) for role in CAMERAS}

    # --- Control ---------------------------------------------------------------------------

    def play(self, action: Mapping[str, Any]) -> int:
        """Execute up to ``execution_horizon`` rows of an approved chunk; returns rows played.

        Call this only through ``GuardedController``. Joint targets and grippers are clamped by
        the actuators' control ranges; the gripper value maps 0..1 to the finger travel.
        """
        right, left = action[ACTION_KEYS["right"]], action[ACTION_KEYS["left"]]
        rows = min(len(right), len(left), self.execution_horizon)
        period = 1.0 / self.action_hz
        played = 0
        for index in range(rows):
            if self._interrupt.is_set():
                break
            started = time.perf_counter()
            with self._lock:
                for arm, row in (("right", right[index]), ("left", left[index])):
                    for act, value in zip(self._joint_ctrl[arm], row[:JOINTS_PER_ARM]):
                        self.data.ctrl[act] = value
                    gripper = float(np.clip(row[JOINTS_PER_ARM], 0.0, 1.0))
                    self.data.ctrl[self._gripper_ctrl[arm]] = gripper * FINGER_OPEN_M
                for _ in range(self.substeps):
                    mujoco.mj_step(self.model, self.data)
                self.rows_played += 1
            played += 1
            if self.realtime:
                time.sleep(max(0.0, period - (time.perf_counter() - started)))
        return played

    def hold(self, seconds: float) -> None:
        """Advance physics without new targets (the arms keep their last approved targets)."""
        steps = max(0, round(seconds / self.model.opt.timestep))
        with self._lock:
            for _ in range(steps):
                mujoco.mj_step(self.model, self.data)

    def interrupt(self) -> None:
        """Stop the chunk being played after the current row (e.g. operator stop)."""
        self._interrupt.set()

    def clear_interrupt(self) -> None:
        self._interrupt.clear()

    def close(self) -> None:
        for renderer in self._renderers:
            renderer.close()
        self._renderers.clear()
        self._local = threading.local()
