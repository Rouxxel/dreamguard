import json

import pytest

from dreamguard import Decision, SafetyConfig, SafetyGuard, Severity, UnsafeActionError
from dreamguard.report import (
    CHECK_WEIGHTS,
    MAX_WARNING_RISK,
    SafetyReport,
    compute_risk,
    violation,
    warning,
)

HOME = [0.0] * 6
CURRENT = {"right": HOME, "left": HOME}


def chunk(*rows):
    return {"q_r_chunk": [list(r) for r in rows], "q_l_chunk": [list(r) for r in rows]}


def test_approved_report_has_approve_decision_and_zero_risk():
    report = SafetyGuard().inspect(chunk(HOME + [0.5]), current_joints=CURRENT)
    assert report.decision is Decision.APPROVE
    assert report.approved
    assert report.risk_score == 0
    assert report.findings == ()


def test_blocked_report_has_block_decision():
    report = SafetyGuard().inspect(chunk(HOME + [2.0]), current_joints=CURRENT)
    assert report.decision is Decision.BLOCK
    assert not report.approved
    assert all(f.severity is Severity.VIOLATION for f in report.violations)


def test_latency_is_measured():
    report = SafetyGuard().inspect(chunk(HOME + [0.5]), current_joints=CURRENT)
    assert report.latency_ms > 0


def test_risk_uses_most_serious_check_plus_two_per_extra_violation():
    findings = [violation("gripper", "a"), violation("joint_limit", "b"), violation("step", "c")]
    assert compute_risk(findings) == CHECK_WEIGHTS["joint_limit"] + 4


def test_risk_is_capped_at_100():
    assert compute_risk([violation("action_format", str(i)) for i in range(10)]) == 100


def test_unknown_check_violation_scores_maximum():
    assert compute_risk([violation("something_new", "x")]) == 100


def test_warnings_score_at_most_fifty_and_do_not_block():
    findings = [warning("joint_limit", "near", weight=999), warning("joint_limit", "far", weight=5)]
    report = SafetyReport.from_findings(findings, checked_rows=1)
    assert report.decision is Decision.APPROVE
    assert report.risk_score == MAX_WARNING_RISK


def test_violation_risk_always_exceeds_warning_risk():
    assert min(CHECK_WEIGHTS.values()) > MAX_WARNING_RISK


def test_report_as_dict_is_json_serializable():
    report = SafetyGuard().inspect(chunk(HOME + [2.0]), current_joints=CURRENT)
    data = json.loads(json.dumps(report.as_dict()))
    assert data["decision"] == "BLOCK"
    assert data["approved"] is False
    assert data["findings"][0]["check"] == "gripper"
    assert data["findings"][0]["severity"] == "violation"
    assert data["findings"][0]["arm"] == "right"
    assert data["findings"][0]["row"] == 0


def test_unsafe_action_error_lists_only_violations():
    config = SafetyConfig(near_limit_margin_rad=0.5)
    near_limit = [3.0, 0, 0, 0, 0, 0, 2.0]
    with pytest.raises(UnsafeActionError) as exc:
        SafetyGuard(config).approve(
            chunk(near_limit), current_joints={"right": near_limit[:6], "left": near_limit[:6]}
        )
    assert "gripper" in str(exc.value)
    assert "comes within" not in str(exc.value)
    assert exc.value.report.warnings
