from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt
from typing import Any, Callable, Mapping, Sequence


Vector3 = tuple[float, float, float]
ForwardKinematics = Callable[[str, Sequence[float]], Vector3]


@dataclass(frozen=True)
class SafetyConfig:
    """Development guardrails; calibrate these against the simulator embodiment."""

    joint_limits: Mapping[str, tuple[tuple[float, float], ...]] = field(
        default_factory=lambda: {
            "right": ((-3.14159, 3.14159),) * 6,
            "left": ((-3.14159, 3.14159),) * 6,
        }
    )
    max_joint_step_rad: float = 0.35
    require_workspace_check: bool = False
    workspace_min_m: Vector3 = (-1.0, -1.0, 0.0)
    workspace_max_m: Vector3 = (1.0, 1.0, 1.5)
    minimum_tool_separation_m: float | None = None


@dataclass(frozen=True)
class SafetyReport:
    approved: bool
    risk_score: int
    findings: tuple[str, ...]
    checked_rows: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "risk_score": self.risk_score,
            "findings": list(self.findings),
            "checked_rows": self.checked_rows,
        }


class UnsafeActionError(RuntimeError):
    def __init__(self, report: SafetyReport):
        self.report = report
        super().__init__("DreamGuard blocked the action: " + "; ".join(report.findings))


def _as_rows(value: Any, key: str) -> list[list[float]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{key} must be a non-empty list of action rows")
    rows: list[list[float]] = []
    for row_index, row in enumerate(value):
        if hasattr(row, "tolist"):
            row = row.tolist()
        if not isinstance(row, (list, tuple)) or len(row) != 7:
            raise ValueError(f"{key}[{row_index}] must contain 7 values: 6 joints + gripper")
        converted: list[float] = []
        for column, raw in enumerate(row):
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"{key}[{row_index}][{column}] is not numeric")
            number = float(raw)
            if not isfinite(number):
                raise ValueError(f"{key}[{row_index}][{column}] is not finite")
            converted.append(number)
        rows.append(converted)
    return rows


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
        findings: list[str] = []
        parsed: dict[str, list[list[float]]] = {}
        checked_rows = 0

        if not isinstance(action, Mapping):
            return SafetyReport(False, 100, ("Action is not a mapping",), 0)

        for arm, key in (("right", "q_r_chunk"), ("left", "q_l_chunk")):
            if key not in action:
                findings.append(f"Missing required action field: {key}")
                continue
            try:
                parsed[arm] = _as_rows(action[key], key)
                checked_rows = max(checked_rows, len(parsed[arm]))
            except ValueError as exc:
                findings.append(str(exc))

        if findings:
            return SafetyReport(False, 100, tuple(findings), checked_rows)

        fk_positions: dict[str, list[Vector3]] = {"right": [], "left": []}

        for arm, rows in parsed.items():
            limits = self.config.joint_limits.get(arm)
            if limits is None or len(limits) != 6:
                findings.append(f"No valid six-joint limits configured for {arm} arm")
                continue

            previous: Sequence[float] | None = None
            if current_joints and arm in current_joints:
                previous = current_joints[arm]
                if len(previous) != 6:
                    findings.append(f"Current {arm} joint state must contain six values")
                    previous = None

            for row_index, row in enumerate(rows):
                joints, gripper = row[:6], row[6]

                for joint_index, (value, bounds) in enumerate(zip(joints, limits)):
                    low, high = bounds
                    if not (low <= value <= high):
                        findings.append(
                            f"{arm} row {row_index}: joint {joint_index} target "
                            f"{value:.3f} outside [{low:.3f}, {high:.3f}] rad"
                        )

                if not 0.0 <= gripper <= 1.0:
                    findings.append(
                        f"{arm} row {row_index}: gripper {gripper:.3f} outside [0, 1]"
                    )

                if previous is not None:
                    largest_step = max(abs(a - b) for a, b in zip(joints, previous))
                    if largest_step > self.config.max_joint_step_rad:
                        findings.append(
                            f"{arm} row {row_index}: joint step {largest_step:.3f} rad "
                            f"exceeds {self.config.max_joint_step_rad:.3f} rad"
                        )
                previous = joints

                if self.forward_kinematics is not None:
                    try:
                        xyz = tuple(
                            float(v) for v in self.forward_kinematics(arm, joints)
                        )
                        if len(xyz) != 3 or not all(isfinite(v) for v in xyz):
                            raise ValueError("FK must return three finite coordinates")
                        fk_positions[arm].append(xyz)  # type: ignore[arg-type]
                        if not all(
                            self.config.workspace_min_m[i] <= xyz[i]
                            <= self.config.workspace_max_m[i]
                            for i in range(3)
                        ):
                            findings.append(
                                f"{arm} row {row_index}: end-effector outside configured workspace"
                            )
                    except Exception as exc:
                        findings.append(f"{arm} row {row_index}: FK check failed: {exc}")
                elif self.config.require_workspace_check:
                    findings.append("Workspace check required but no FK callback was supplied")
                    break

        if self.config.minimum_tool_separation_m is not None:
            if self.forward_kinematics is None:
                findings.append("Tool-separation check requires a forward-kinematics callback")
            elif len(fk_positions["right"]) == len(fk_positions["left"]):
                for index, (right, left) in enumerate(
                    zip(fk_positions["right"], fk_positions["left"])
                ):
                    distance = sqrt(sum((right[i] - left[i]) ** 2 for i in range(3)))
                    if distance < self.config.minimum_tool_separation_m:
                        findings.append(
                            f"Row {index}: end-effector separation {distance:.3f} m "
                            f"is below {self.config.minimum_tool_separation_m:.3f} m"
                        )
            else:
                findings.append("Cannot compare end-effectors: FK results are incomplete")

        approved = not findings
        risk_score = 0 if approved else min(100, 60 + 10 * len(findings))
        return SafetyReport(approved, risk_score, tuple(findings), checked_rows)

    def approve(
        self,
        action: Mapping[str, Any],
        *,
        current_joints: Mapping[str, Sequence[float]] | None = None,
    ) -> dict[str, Any]:
        report = self.inspect(action, current_joints=current_joints)
        if not report.approved:
            raise UnsafeActionError(report)
        # Preserve Dream-1's other metadata fields; validated chunks are copied.
        approved = dict(action)
        for key in ("q_r_chunk", "q_l_chunk"):
            rows = action[key].tolist() if hasattr(action[key], "tolist") else action[key]
            approved[key] = [list(row) for row in rows]
        return approved
