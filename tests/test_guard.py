import numpy as np
import pytest

from dreamguard.guard import SafetyConfig, SafetyGuard, UnsafeActionError

HOME = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
CURRENT = {"right": list(HOME), "left": list(HOME)}


def action():
    row = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5]
    next_row = [0.05, 0.02, 0.0, 0.0, 0.0, 0.0, 0.5]
    return {"q_r_chunk": [row, next_row], "q_l_chunk": [list(row), list(next_row)]}


def inspect(act, guard=None, current=CURRENT):
    return (guard or SafetyGuard()).inspect(act, current_joints=current)


def findings_text(report):
    return " ".join(report.findings)


# --- Original starter behaviour ------------------------------------------------


def test_safe_action_is_approved():
    report = inspect(action())
    assert report.approved
    assert report.risk_score == 0


def test_missing_arm_chunk_fails_closed():
    report = inspect({"q_r_chunk": action()["q_r_chunk"]})
    assert not report.approved
    assert "q_l_chunk" in findings_text(report)


def test_large_joint_step_is_blocked():
    bad = action()
    bad["q_r_chunk"][1][0] = 1.0
    with pytest.raises(UnsafeActionError):
        SafetyGuard(SafetyConfig(max_joint_step_rad=0.2)).approve(bad, current_joints=CURRENT)


def test_joint_limit_is_enforced():
    bad = action()
    bad["q_l_chunk"][0][0] = 4.0
    assert not inspect(bad).approved


def test_gripper_range_is_enforced():
    bad = action()
    bad["q_r_chunk"][0][6] = 1.5
    assert not inspect(bad).approved


def test_nan_is_blocked():
    bad = action()
    bad["q_l_chunk"][0][2] = float("nan")
    assert not inspect(bad).approved


def test_fk_workspace_check_can_be_required():
    guard = SafetyGuard(
        SafetyConfig(require_workspace_check=True),
        forward_kinematics=lambda arm, joints: (0.0, 0.0, 0.5),
    )
    assert inspect(action(), guard).approved


# --- D1: current joint state must be valid ---------------------------------------


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_current_state_is_blocked(bad_value):
    current = {"right": [bad_value] * 6, "left": list(HOME)}
    report = inspect(action(), current=current)
    assert not report.approved
    assert "Current right joint state" in findings_text(report)


def test_current_state_with_wrong_length_is_blocked():
    current = {"right": [0.0] * 5, "left": list(HOME)}
    assert not inspect(action(), current=current).approved


def test_non_numeric_current_state_is_blocked():
    current = {"right": ["0.0"] * 6, "left": list(HOME)}
    assert not inspect(action(), current=current).approved


def test_numpy_float32_current_state_is_accepted():
    current = {"right": np.zeros(6, dtype=np.float32), "left": np.zeros(6, dtype=np.float32)}
    assert inspect(action(), current=current).approved


# --- D2: current state is mandatory and row 0 is checked against it --------------


def test_missing_current_state_fails_closed_by_default():
    report = inspect(action(), current=None)
    assert not report.approved
    assert "required" in findings_text(report)


def test_missing_current_state_for_one_arm_fails_closed():
    assert not inspect(action(), current={"right": list(HOME)}).approved


def test_first_row_jump_from_current_state_is_blocked():
    far = [3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5]
    report = inspect({"q_r_chunk": [far], "q_l_chunk": [far]})
    assert not report.approved
    assert "row 0: joint step" in findings_text(report)


def test_current_state_can_be_made_optional_explicitly():
    guard = SafetyGuard(SafetyConfig(require_current_state=False))
    assert inspect(action(), guard, current=None).approved


# --- D3: numpy scalars accepted, booleans rejected -------------------------------


def test_rows_of_numpy_float32_scalars_are_accepted():
    row = [np.float32(0.0)] * 6 + [np.float32(0.5)]
    assert inspect({"q_r_chunk": [row], "q_l_chunk": [row]}).approved


def test_numpy_array_chunks_are_accepted():
    chunk = np.zeros((3, 7), dtype=np.float32)
    chunk[:, 6] = 0.5
    assert inspect({"q_r_chunk": chunk, "q_l_chunk": chunk.copy()}).approved


@pytest.mark.parametrize("bool_value", [True, np.bool_(True)])
def test_boolean_values_are_rejected(bool_value):
    bad = action()
    bad["q_r_chunk"][0][1] = bool_value
    report = inspect(bad)
    assert not report.approved
    assert "not numeric" in findings_text(report)


# --- D4: chunk length bounds and arm consistency ---------------------------------


def test_arm_chunks_with_different_lengths_are_blocked():
    row = [0.0] * 6 + [0.5]
    report = inspect({"q_r_chunk": [row] * 50, "q_l_chunk": [row] * 3})
    assert not report.approved
    assert "different lengths" in findings_text(report)


def test_chunk_longer_than_max_rows_is_blocked():
    row = [0.0] * 6 + [0.5]
    guard = SafetyGuard(SafetyConfig(max_rows=10))
    report = inspect({"q_r_chunk": [row] * 11, "q_l_chunk": [row] * 11}, guard)
    assert not report.approved
    assert "rows" in findings_text(report)


def test_chunk_shorter_than_min_rows_is_blocked():
    guard = SafetyGuard(SafetyConfig(min_rows=3))
    assert not inspect(action(), guard).approved


def test_empty_chunk_is_blocked():
    assert not inspect({"q_r_chunk": [], "q_l_chunk": []}).approved


# --- Workspace, forward kinematics and separation --------------------------------


def test_end_effector_outside_workspace_is_blocked():
    guard = SafetyGuard(forward_kinematics=lambda arm, joints: (5.0, 0.0, 0.5))
    report = inspect(action(), guard)
    assert not report.approved
    assert "outside configured workspace" in findings_text(report)


def test_required_workspace_check_without_fk_is_blocked():
    guard = SafetyGuard(SafetyConfig(require_workspace_check=True))
    report = inspect(action(), guard)
    assert not report.approved
    assert "no FK callback" in findings_text(report)


def test_fk_exception_fails_closed():
    def broken_fk(arm, joints):
        raise RuntimeError("solver diverged")

    report = inspect(action(), SafetyGuard(forward_kinematics=broken_fk))
    assert not report.approved
    assert "FK check failed" in findings_text(report)


@pytest.mark.parametrize("bad_xyz", [(float("nan"), 0.0, 0.5), (0.0, 0.5), (0.0, 0.0, 0.5, 1.0)])
def test_invalid_fk_output_fails_closed(bad_xyz):
    report = inspect(action(), SafetyGuard(forward_kinematics=lambda arm, joints: bad_xyz))
    assert not report.approved


def test_end_effectors_too_close_are_blocked():
    guard = SafetyGuard(
        SafetyConfig(minimum_tool_separation_m=0.10),
        forward_kinematics=lambda arm, joints: (0.0, 0.02 if arm == "right" else -0.02, 0.5),
    )
    report = inspect(action(), guard)
    assert not report.approved
    assert "separation" in findings_text(report)


def test_end_effectors_far_enough_apart_are_approved():
    guard = SafetyGuard(
        SafetyConfig(minimum_tool_separation_m=0.10),
        forward_kinematics=lambda arm, joints: (0.0, 0.3 if arm == "right" else -0.3, 0.5),
    )
    assert inspect(action(), guard).approved


def test_separation_check_without_fk_fails_closed():
    guard = SafetyGuard(SafetyConfig(minimum_tool_separation_m=0.10))
    assert not inspect(action(), guard).approved
