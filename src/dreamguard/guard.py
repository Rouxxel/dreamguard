from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Any

from .checks import (
    ACTION_KEYS,
    ForwardKinematics,
    check_chunk_shape,
    check_gripper,
    check_joint_limits,
    check_separation,
    check_steps,
    check_velocity,
    check_workspace,
    compute_end_effectors,
    parse_action,
    parse_current_state,
)
from .config import SafetyConfig, Vector3
from .report import Decision, Finding, SafetyReport, UnsafeActionError, violation

__all__ = [
    "Decision",
    "Finding",
    "ForwardKinematics",
    "SafetyConfig",
    "SafetyGuard",
    "SafetyReport",
    "UnsafeActionError",
    "Vector3",
]


def approved_copy(action: Mapping[str, Any]) -> dict[str, Any]:
    """Copy of an approved action: Dream-1 metadata kept, arm chunks copied as plain lists.

    Copying means later changes to the caller's objects cannot alter what is executed.
    """
    approved = dict(action)
    for key in ACTION_KEYS.values():
        rows = action[key].tolist() if hasattr(action[key], "tolist") else action[key]
        approved[key] = [list(row) for row in rows]
    return approved


class SafetyGuard:
    """Inspects Dream-1 YAM action chunks and approves or blocks them."""

    def __init__(
        self,
        config: SafetyConfig | None = None,
        *,
        forward_kinematics: ForwardKinematics | None = None,
    ):
        self.config = config or SafetyConfig()
        self.forward_kinematics = forward_kinematics

    def inspect(
        self,
        action: Mapping[str, Any],
        *,
        current_joints: Mapping[str, Sequence[float]] | None = None,
    ) -> SafetyReport:
        started = perf_counter()
        findings, checked_rows = self._evaluate(action, current_joints)
        latency_ms = (perf_counter() - started) * 1000.0
        return SafetyReport.from_findings(findings, checked_rows, latency_ms)

    def approve(
        self,
        action: Mapping[str, Any],
        *,
        current_joints: Mapping[str, Sequence[float]] | None = None,
    ) -> dict[str, Any]:
        report = self.inspect(action, current_joints=current_joints)
        if report.decision is not Decision.APPROVE:
            raise UnsafeActionError(report)
        return approved_copy(action)

    def _evaluate(
        self,
        action: Mapping[str, Any],
        current_joints: Mapping[str, Sequence[float]] | None,
    ) -> tuple[list[Finding], int]:
        config = self.config
        parsed, findings = parse_action(action)
        checked_rows = max((len(rows) for rows in parsed.values()), default=0)
        if findings:
            return findings, checked_rows

        findings += check_chunk_shape(parsed, config.min_rows, config.max_rows)
        current, state_findings = parse_current_state(
            current_joints, required=config.require_current_state
        )
        findings += state_findings
        if findings:
            return findings, checked_rows

        positions: dict[str, list[Vector3 | None]] = {}
        for arm, rows in parsed.items():
            findings += check_joint_limits(
                arm, rows, config.joint_limits[arm], config.near_limit_margin_rad
            )
            findings += check_gripper(arm, rows, config.gripper_range)
            findings += check_steps(arm, rows, current.get(arm), config.max_joint_step_rad)
            if config.max_joint_velocity_rad_s is not None:
                findings += check_velocity(
                    arm, rows, config.max_joint_velocity_rad_s, config.action_hz
                )
            if self.forward_kinematics is not None:
                positions[arm], fk_findings = compute_end_effectors(
                    arm, rows, self.forward_kinematics
                )
                findings += fk_findings
                findings += check_workspace(
                    arm, positions[arm], config.workspace_min_m, config.workspace_max_m
                )

        if self.forward_kinematics is None and config.require_workspace_check:
            findings.append(
                violation("workspace", "Workspace check required but no FK callback was supplied")
            )
        if config.minimum_tool_separation_m is not None:
            if self.forward_kinematics is None:
                findings.append(
                    violation(
                        "separation",
                        "Tool-separation check requires a forward-kinematics callback",
                    )
                )
            else:
                findings += check_separation(positions, config.minimum_tool_separation_m)
        return findings, checked_rows
