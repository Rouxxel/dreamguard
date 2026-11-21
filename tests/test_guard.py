import pytest

from dreamguard.guard import SafetyConfig, SafetyGuard, UnsafeActionError


def action():
    row = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5]
    next_row = [0.05, 0.02, 0.0, 0.0, 0.0, 0.0, 0.5]
    return {"q_r_chunk": [row, next_row], "q_l_chunk": [row, next_row]}


def test_safe_action_is_approved():
    report = SafetyGuard().inspect(action())
    assert report.approved
    assert report.risk_score == 0


def test_missing_arm_chunk_fails_closed():
    report = SafetyGuard().inspect({"q_r_chunk": action()["q_r_chunk"]})
    assert not report.approved
    assert "q_l_chunk" in " ".join(report.findings)


def test_large_joint_step_is_blocked():
    bad = action()
    bad["q_r_chunk"][1][0] = 1.0
    with pytest.raises(UnsafeActionError):
        SafetyGuard(SafetyConfig(max_joint_step_rad=0.2)).approve(bad)


def test_joint_limit_is_enforced():
    bad = action()
    bad["q_l_chunk"][0][0] = 4.0
    assert not SafetyGuard().inspect(bad).approved


def test_gripper_range_is_enforced():
    bad = action()
    bad["q_r_chunk"][0][6] = 1.5
    assert not SafetyGuard().inspect(bad).approved


def test_nan_is_blocked():
    bad = action()
    bad["q_l_chunk"][0][2] = float("nan")
    assert not SafetyGuard().inspect(bad).approved


def test_fk_workspace_check_can_be_required():
    guard = SafetyGuard(
        SafetyConfig(require_workspace_check=True),
        forward_kinematics=lambda arm, joints: (0.0, 0.0, 0.5),
    )
    assert guard.inspect(action()).approved
