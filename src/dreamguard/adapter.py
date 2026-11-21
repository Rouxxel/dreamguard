"""Connects DreamGuard to a Dream-1 client and a robot controller."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from .events import EventBus, SafetyEvent, new_session_id, validate_session_id
from .guard import SafetyGuard, approved_copy
from .report import Decision, SafetyReport

logger = logging.getLogger(__name__)

OBSERVATION_STATE_KEYS = {"right": "state.right_arm", "left": "state.left_arm"}


class Robot(Protocol):
    def play(self, action: Mapping[str, Any]) -> Any: ...


class ControllerHaltedError(RuntimeError):
    """Raised when the controller stopped after repeated blocked actions."""


def current_joints_from_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Measured arm joints from a Dream-1 observation; missing arms are left out (and blocked)."""
    return {
        arm: observation[key] for arm, key in OBSERVATION_STATE_KEYS.items() if key in observation
    }


def guarded_get_action(
    client: Any,
    guard: SafetyGuard,
    observation: Mapping[str, Any] | None = None,
    *,
    current_joints: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    """Get one Dream-1 action chunk and fail closed unless DreamGuard approves it.

    The measured joint state comes from ``current_joints`` or, if omitted, from the
    ``state.right_arm`` / ``state.left_arm`` entries of ``observation``.
    """
    if current_joints is None and observation is not None:
        current_joints = current_joints_from_observation(observation)
    action = client.get_action()
    return guard.approve(action, current_joints=current_joints)


class GuardedController:
    """The only object that calls ``robot.play``; every action is inspected first.

    - APPROVE: the validated action is played and the consecutive-block counter resets.
    - BLOCK: nothing is played (the robot keeps its last approved targets) and ``on_block`` runs.
      After ``max_consecutive_blocks`` blocks in a row the controller halts and refuses further
      actions until ``reset()`` is called.

    Every decision is published to ``bus`` as a ``SafetyEvent``.
    """

    def __init__(
        self,
        robot: Robot,
        guard: SafetyGuard,
        *,
        bus: EventBus | None = None,
        session_id: str | None = None,
        source: str = "",
        max_consecutive_blocks: int = 3,
        on_block: Callable[[SafetyReport], None] | None = None,
    ) -> None:
        if max_consecutive_blocks < 1:
            raise ValueError("max_consecutive_blocks must be >= 1")
        self._robot = robot
        self._guard = guard
        self._bus = bus or EventBus()
        self._lock = threading.Lock()
        self.session_id = validate_session_id(session_id or new_session_id())
        self.source = source
        self.max_consecutive_blocks = max_consecutive_blocks
        self.on_block = on_block
        self.sequence = 0
        self.consecutive_blocks = 0
        self.halted = False

    @property
    def bus(self) -> EventBus:
        return self._bus

    def submit(
        self,
        action: Mapping[str, Any],
        *,
        current_joints: Mapping[str, Sequence[float]] | None = None,
        observation: Mapping[str, Any] | None = None,
    ) -> SafetyReport:
        """Inspect one action chunk and play it only if it is approved."""
        if current_joints is None and observation is not None:
            current_joints = current_joints_from_observation(observation)
        with self._lock:
            if self.halted:
                raise ControllerHaltedError(
                    f"Controller halted after {self.consecutive_blocks} consecutive blocked "
                    "actions; call reset() after reviewing the cause"
                )
            report = self._guard.inspect(action, current_joints=current_joints)
            self.sequence += 1
            executed, error = False, None
            try:
                if report.decision is Decision.APPROVE:
                    self.consecutive_blocks = 0
                    self._robot.play(approved_copy(action))
                    executed = True
                else:
                    self.consecutive_blocks += 1
                    self.halted = self.consecutive_blocks >= self.max_consecutive_blocks
                    if self.on_block is not None:
                        self.on_block(report)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                self._bus.publish(
                    SafetyEvent(
                        session_id=self.session_id,
                        sequence=self.sequence,
                        report=report,
                        executed=executed,
                        action=action if isinstance(action, Mapping) else {},
                        current_joints=current_joints,
                        source=self.source,
                        halted=self.halted,
                        error=error,
                    )
                )
            if self.halted:
                logger.warning("DreamGuard controller halted (session %s)", self.session_id)
            return report

    def reset(self) -> None:
        """Clear a halt after an operator has reviewed the blocked actions."""
        with self._lock:
            self.halted = False
            self.consecutive_blocks = 0
