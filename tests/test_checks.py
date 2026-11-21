import pytest

from dreamguard import SafetyConfig, SafetyGuard, Severity
from dreamguard.checks import (
    check_chunk_shape,
    check_gripper,
    check_joint_limits,
    check_separation,
    check_steps,
    check_velocity,
    check_workspace,
    compute_end_effectors,
    parse_action,
)

LIMITS = ((-1.0, 1.0),) * 6
HOME = [0.0] * 6


def row(joints=HOME, gripper=0.5):
    return list(joints) + [gripper]


# --- Velocity ---------------------------------------------------------------------------


def test_velocity_within_limit_passes():
    rows = [row(), row([0.1, 0, 0, 0, 0, 0])]  # 0.1 rad in 1/20 s = 2 rad/s
    assert check_velocity("right", rows, (3.0,) * 6, action_hz=20.0) == []


def test_velocity_over_limit_reports_worst_joint():
    rows = [row(), row([0.1, 0, 0.2, 0, 0, 0])]  # joint 2: 4 rad/s
    [finding] = check_velocity("right", rows, (3.0,) * 6, action_hz=20.0)
    assert finding.check == "velocity"
    assert finding.joint == 2
    assert finding.value == pytest.approx(4.0)
    assert finding.limit == 3.0


def test_velocity_uses_per_joint_limits():
    rows = [row(), row([0.1, 0, 0, 0, 0, 0])]  # joint 0: 2 rad/s
    limits = (1.5, 3.0, 3.0, 3.0, 3.0, 3.0)
    assert check_velocity("left", rows, limits, action_hz=20.0)[0].joint == 0


def test_velocity_depends_on_action_rate():
    rows = [row(), row([0.1, 0, 0, 0, 0, 0])]
    assert check_velocity("right", rows, (3.0,) * 6, action_hz=20.0) == []
    assert check_velocity("right", rows, (3.0,) * 6, action_hz=40.0)  # 4 rad/s


def test_velocity_ignores_row_zero_against_current_state():
    assert check_velocity("right", [row([0.3] * 6)], (1.0,) * 6, action_hz=20.0) == []


def test_guard_applies_velocity_limit_when_configured():
    action = {"q_r_chunk": [row(), row([0.2] + HOME[1:])], "q_l_chunk": [row(), row()]}
    current = {"right": HOME, "left": HOME}
    assert SafetyGuard().inspect(action, current_joints=current).approved
    guard = SafetyGuard(SafetyConfig(max_joint_velocity_rad_s=(3.0,) * 6))
    report = guard.inspect(action, current_joints=current)
    assert not report.approved
    assert report.violations[0].check == "velocity"


# --- Joint limits and near-limit warnings -------------------------------------------------


def test_joint_outside_limit_is_violation_with_details():
    [finding] = check_joint_limits("left", [row([0, 0, 1.2, 0, 0, 0])], LIMITS)
    assert finding.severity is Severity.VIOLATION
    assert (finding.arm, finding.row, finding.joint) == ("left", 0, 2)
    assert finding.limit == 1.0


def test_target_inside_margin_is_single_warning_at_closest_row():
    rows = [row([0.92] + HOME[1:]), row([0.98] + HOME[1:]), row([0.95] + HOME[1:])]
    [finding] = check_joint_limits("right", rows, LIMITS, near_limit_margin=0.1)
    assert finding.severity is Severity.WARNING
    assert finding.row == 1
    assert finding.weight == 40  # 0.02 rad from the limit with a 0.1 rad margin


def test_no_warning_when_margin_disabled():
    assert check_joint_limits("right", [row([0.999] + HOME[1:])], LIMITS) == []


def test_target_exactly_on_limit_is_allowed_with_full_warning():
    [finding] = check_joint_limits("right", [row([1.0] + HOME[1:])], LIMITS, 0.1)
    assert finding.severity is Severity.WARNING
    assert finding.weight == 50


def test_near_limit_warning_does_not_block_but_raises_risk():
    guard = SafetyGuard(SafetyConfig(near_limit_margin_rad=0.2))
    near = [3.1, 0, 0, 0, 0, 0]
    report = guard.inspect(
        {"q_r_chunk": [near + [0.5]], "q_l_chunk": [HOME + [0.5]]},
        current_joints={"right": near, "left": HOME},
    )
    assert report.approved
    assert 0 < report.risk_score <= 50


# --- Gripper, steps and shape -------------------------------------------------------------


def test_gripper_range_is_configurable():
    rows = [row(gripper=0.9)]
    assert check_gripper("right", rows, (0.0, 1.0)) == []
    assert check_gripper("right", rows, (0.0, 0.8))[0].limit == 0.8


def test_step_finding_reports_largest_joint():
    rows = [row([0, 0, 0, 0.5, 0, 0])]
    [finding] = check_steps("right", rows, HOME, max_step=0.35)
    assert finding.joint == 3
    assert finding.row == 0


def test_steps_without_start_only_compare_consecutive_rows():
    rows = [row([0.9] * 6), row([0.9] * 6)]
    assert check_steps("right", rows, None, max_step=0.1) == []


def test_chunk_shape_accepts_equal_lengths_within_bounds():
    assert check_chunk_shape({"right": [row()] * 3, "left": [row()] * 3}, 1, 5) == []


def test_parse_action_rejects_non_mapping():
    parsed, findings = parse_action([1, 2])
    assert parsed == {}
    assert findings[0].check == "action_format"


# --- FK, workspace, separation ------------------------------------------------------------


def test_compute_end_effectors_marks_failed_rows():
    calls = iter([(0.0, 0.0, 0.5), ValueError("singular")])

    def fk(arm, joints):
        result = next(calls)
        if isinstance(result, Exception):
            raise result
        return result

    positions, findings = compute_end_effectors("right", [row(), row()], fk)
    assert positions == [(0.0, 0.0, 0.5), None]
    assert findings[0].check == "fk"
    assert findings[0].row == 1


def test_workspace_skips_failed_fk_rows():
    positions = [None, (5.0, 0.0, 0.0)]
    [finding] = check_workspace("left", positions, (-1, -1, 0), (1, 1, 1))
    assert finding.row == 1


def test_separation_with_incomplete_fk_fails_closed():
    findings = check_separation({"right": [(0, 0, 0)], "left": [None]}, 0.1)
    assert findings[0].check == "separation"
    assert "incomplete" in findings[0].message
