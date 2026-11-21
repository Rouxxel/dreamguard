"""Synchronous Dream-1 style control loop: observe, get an action, let DreamGuard decide."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..adapter import ControllerHaltedError, GuardedController
from ..report import SafetyReport
from ..sources.replay import ReplayExhaustedError
from .robot import SimRobot


@dataclass
class LoopResult:
    reports: list[SafetyReport] = field(default_factory=list)
    halted: bool = False
    exhausted: bool = False


def run_loop(
    client: Any,
    robot: SimRobot,
    controller: GuardedController,
    *,
    chunks: int,
    prompt: str = "",
    render_frames: bool = True,
    before_chunk: Callable[[int], None] | None = None,
) -> LoopResult:
    """Run ``chunks`` observe -> get_action -> guarded play iterations.

    The client must already have a policy. ``render_frames=False`` skips camera rendering for
    clients that ignore frames (fake / replay sources), which keeps tests fast.
    """
    result = LoopResult()
    for index in range(chunks):
        if before_chunk is not None:
            before_chunk(index)
        observation = robot.observation(prompt)
        client.set_observation(robot.frames() if render_frames else {}, observation)
        try:
            action = client.get_action()
        except ReplayExhaustedError:
            result.exhausted = True
            break
        try:
            result.reports.append(controller.submit(action, observation=observation))
        except ControllerHaltedError:
            result.halted = True
            break
        if controller.halted:
            result.halted = True
            break
    return result
