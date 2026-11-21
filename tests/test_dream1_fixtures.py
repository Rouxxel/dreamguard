from pathlib import Path

import pytest

from dreamguard import Decision, SafetyGuard, load_builtin_profile
from dreamguard.events import read_session

FIXTURES = sorted((Path(__file__).resolve().parents[1] / "fixtures" / "dream1").glob("*.jsonl"))


@pytest.fixture(scope="module")
def guard():
    pytest.importorskip("mujoco")
    from dreamguard.sim import SimKinematics

    return SafetyGuard(load_builtin_profile("yam_sim"), forward_kinematics=SimKinematics())


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.stem for f in FIXTURES])
def test_recorded_dream1_chunks_pass_the_yam_profile(guard, fixture):
    """Real Dream-1 replies must not be falsely rejected by the simulator profile."""
    replies = [line for line in read_session(fixture) if line.get("action")]
    assert replies, "fixture has no recorded actions"
    for reply in replies:
        state = reply["observation_state"]
        current = {"right": state["state.right_arm"], "left": state["state.left_arm"]}
        report = guard.inspect(reply["action"], current_joints=current)
        assert report.decision is Decision.APPROVE, report.messages
