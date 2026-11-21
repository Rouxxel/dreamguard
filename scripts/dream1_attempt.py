"""Live Dream-1 attempts in the MuJoCo simulator, with DreamGuard in the loop.

Preflight (no inference):
    python scripts/dream1_attempt.py --preflight                       # offline, no network
    python scripts/dream1_attempt.py --preflight --allow-model-lookup  # + one GET /v1/models

Paid attempt (each get_action() is a paid inference call):
    $env:DREAMGUARD_ALLOW_PAID = "1"
    python scripts/dream1_attempt.py --max-calls 1 --i-approve-paid-calls --prompt "..."

Nothing is sent unless --i-approve-paid-calls is given, DREAMGUARD_ALLOW_PAID=1 is set and
--max-calls (the hard budget) is at least 1. Every reply is recorded to fixtures/dream1/ and the
session to logs/sessions/, so both can be replayed for free.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

from dreamguard import SafetyGuard, load_builtin_profile
from dreamguard.adapter import GuardedController
from dreamguard.demo import format_report
from dreamguard.events import EventBus, JsonlSessionRecorder
from dreamguard.sim import SimKinematics, SimRobot
from dreamguard.sources.dream1 import Dream1Source, PaidCallBudgetExhausted, preflight

FIXTURES_DIR = REPO_ROOT / "fixtures" / "dream1"
SESSIONS_DIR = REPO_ROOT / "backend" / "logs" / "sessions"  # shown on the dashboard


def joint_offsets(action: dict, current: dict) -> dict[str, list[float]]:
    """First-row target minus measured joints, per arm.

    Large offsets on a still robot hint at a joint zero / sign convention mismatch between
    Dream-1 and the simulator model.
    """
    offsets = {}
    for arm, key in (("right", "q_r_chunk"), ("left", "q_l_chunk")):
        rows = action.get(key) or []
        if rows:
            first, measured = rows[0][:6], current[arm]
            offsets[arm] = [round(float(t) - float(c), 3) for t, c in zip(first, measured)]
    return offsets


def run_attempt(args: argparse.Namespace) -> int:
    robot = SimRobot(realtime=True)
    fk = SimKinematics(robot.model)
    guard = SafetyGuard(load_builtin_profile("yam_sim"), forward_kinematics=fk)
    bus = EventBus()
    recorder = JsonlSessionRecorder(SESSIONS_DIR)
    bus.subscribe(recorder)
    source = Dream1Source(max_calls=args.max_calls, fixtures_dir=FIXTURES_DIR)
    controller = GuardedController(
        robot, guard, bus=bus, session_id=source.session_id, source="dream1",
        max_consecutive_blocks=args.max_calls + 1,
    )
    print(f"Session {source.session_id}: up to {args.max_calls} paid get_action() call(s)\n")
    try:
        source.policy()
        for index in range(1, args.max_calls + 1):
            observation = robot.observation(args.prompt)
            current = robot.current_joints()
            source.set_observation(robot.frames(), observation)
            try:
                action = source.get_action()
            except PaidCallBudgetExhausted:
                break
            report = controller.submit(action, observation=observation)
            title = f"Dream-1 chunk ({len(action.get('q_r_chunk', []))} rows)"
            print(format_report(index, title, report))
            print(f"  first-row offset from measured joints: {joint_offsets(action, current)}")
            print(f"  round trip: {json.dumps(source._client.last_timing)}\n")
    finally:
        source.close()
        robot.close()
    print(f"Paid calls made: {source.calls}")
    print(f"Replies recorded: {source.fixture_path}")
    print(f"Session recorded: {recorder.path_for(source.session_id)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Dream-1 attempts with DreamGuard")
    parser.add_argument("--prompt", default="tidy up the table")
    parser.add_argument("--preflight", action="store_true", help="check inputs; no inference")
    parser.add_argument("--allow-model-lookup", action="store_true",
                        help="preflight also opens the policy (one GET /v1/models request)")
    parser.add_argument("--max-calls", type=int, default=0, help="hard budget of paid calls")
    parser.add_argument("--i-approve-paid-calls", action="store_true")
    args = parser.parse_args(argv)

    if args.preflight:
        robot = SimRobot()
        try:
            result = preflight(
                robot, prompt=args.prompt, allow_model_lookup=args.allow_model_lookup
            )
        finally:
            robot.close()
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    refusals = []
    if not args.i_approve_paid_calls:
        refusals.append("--i-approve-paid-calls is required")
    if os.getenv("DREAMGUARD_ALLOW_PAID", "0").strip() != "1":
        refusals.append("DREAMGUARD_ALLOW_PAID=1 is required")
    if args.max_calls < 1:
        refusals.append("--max-calls must be at least 1")
    if refusals:
        print("Refusing to make paid calls: " + "; ".join(refusals), file=sys.stderr)
        return 2
    return run_attempt(args)


if __name__ == "__main__":
    raise SystemExit(main())
