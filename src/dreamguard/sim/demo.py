"""Offline simulator run: scripted chunks, then every fault, all through DreamGuard.

Run with ``python -m dreamguard.sim.demo``. No network access and no Dream credits are used.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from ..adapter import GuardedController
from ..config import load_builtin_profile
from ..demo import format_report
from ..events import EventBus, JsonlSessionRecorder
from ..guard import SafetyGuard
from ..sources.fake import FAULTS, FakeDreamClient
from .kinematics import SimKinematics
from .loop import run_loop
from .robot import SimRobot


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clean-chunks", type=int, default=6)
    parser.add_argument("--sessions-dir", default="logs/sessions")
    parser.add_argument("--snapshot", default="logs/sim_overhead.png")
    args = parser.parse_args(argv)

    robot = SimRobot()
    profile = load_builtin_profile("yam_sim")
    guard = SafetyGuard(profile, forward_kinematics=SimKinematics(robot.model))
    bus = EventBus()
    recorder = JsonlSessionRecorder(args.sessions_dir)
    bus.subscribe(recorder)
    controller = GuardedController(robot, guard, bus=bus, source="fake", max_consecutive_blocks=99)
    client = FakeDreamClient()
    client.policy({"checkpoint": "offline-fake"})

    print("DreamGuard Safety Supervisor - offline MuJoCo run\n")
    scenarios = [("scripted motion", None)] * args.clean_chunks + [
        (f"fault: {name} - {description}", name) for name, description in FAULTS.items()
    ]
    blocked = unsafe = 0
    for index, (title, fault) in enumerate(scenarios, start=1):
        if fault is not None:
            client.inject(fault)
            unsafe += 1
        report = run_loop(client, robot, controller, chunks=1, render_frames=False).reports[0]
        blocked += not report.approved
        print(format_report(index, title, report) + "\n")

    snapshot = Path(args.snapshot)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(robot.render("overhead")).save(snapshot)
    robot.close()
    print(f"Evaluated {len(scenarios)} chunks: {unsafe} unsafe injected, {blocked} blocked, "
          f"{robot.rows_played} rows executed.")
    print(f"Session log: {recorder.path_for(controller.session_id)}")
    print(f"Overhead snapshot: {snapshot}")


if __name__ == "__main__":
    main()
