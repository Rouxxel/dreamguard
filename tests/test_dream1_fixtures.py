from pathlib import Path

import pytest

from dreamguard import Decision, SafetyGuard, load_builtin_profile
from dreamguard.events import read_session

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "dream1"

# Expected yam_sim decision per recorded live Dream-1 reply (A = approve, B = block).
# Attempt 3 ends with the right arm folded against joint2/joint3's 0 rad hard stop: Dream-1
# commands targets up to 0.0196 rad past it, which the strict joint limits correctly block.
EXPECTED = {
    "20261121T213830Z-b07e9f08": "A",
    "20261121T214235Z-5473a8ce": "AAAAAAAAAA",
    "20261121T215356Z-ed761785": "AAAAAAAAAAA" + "BBBBBBBBB",
}


@pytest.fixture(scope="module")
def guard():
    pytest.importorskip("mujoco")
    from dreamguard.sim import SimKinematics

    return SafetyGuard(load_builtin_profile("yam_sim"), forward_kinematics=SimKinematics())


def test_every_recorded_fixture_has_expectations():
    assert {path.stem for path in FIXTURES_DIR.glob("*.jsonl")} == set(EXPECTED)


@pytest.mark.parametrize("session", sorted(EXPECTED))
def test_recorded_dream1_decisions_are_stable(guard, session):
    """Real Dream-1 replies keep their decisions; blocks come only from real limit excursions."""
    recorded = read_session(FIXTURES_DIR / f"{session}.jsonl")
    replies = [line for line in recorded if line.get("action")]
    decisions = ""
    for reply in replies:
        state = reply["observation_state"]
        current = {"right": state["state.right_arm"], "left": state["state.left_arm"]}
        report = guard.inspect(reply["action"], current_joints=current)
        decisions += "A" if report.decision is Decision.APPROVE else "B"
        if not report.approved:
            assert {f.check for f in report.violations} == {"joint_limit"}, report.messages
            assert all(abs(f.value - f.limit) <= 0.02 for f in report.violations)
    assert decisions == EXPECTED[session]
