"""Pure safety checks. Each function inspects parsed values and returns findings."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from math import isfinite, sqrt
from numbers import Real
from typing import Any

from .config import ARMS, JOINTS_PER_ARM, JointLimits, Vector3
from .report import MAX_WARNING_RISK, Finding, violation, warning

ForwardKinematics = Callable[[str, Sequence[float]], Vector3]
ROW_WIDTH = JOINTS_PER_ARM + 1  # six joint targets followed by the gripper
ACTION_KEYS = {"right": "q_r_chunk", "left": "q_l_chunk"}

Rows = list[list[float]]


# --- Parsing -------------------------------------------------------------------------


def _as_number(raw: Any, label: str) -> float:
    # numbers.Real covers Python and NumPy numeric scalars; bool and np.bool_ are rejected.
    if isinstance(raw, bool) or not isinstance(raw, Real):
        raise ValueError(f"{label} is not numeric")  # noqa: TRY004
    number = float(raw)
    if not isfinite(number):
        raise ValueError(f"{label} is not finite")
    return number


def _as_vector(value: Any, length: int, label: str, description: str) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"{label} must contain {length} values: {description}")
    return [_as_number(raw, f"{label}[{index}]") for index, raw in enumerate(value)]


def _as_rows(value: Any, key: str) -> Rows:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{key} must be a non-empty list of action rows")
    return [
        _as_vector(row, ROW_WIDTH, f"{key}[{row_index}]", "6 joints + gripper")
        for row_index, row in enumerate(value)
    ]


def parse_action(action: Any) -> tuple[dict[str, Rows], list[Finding]]:
    """Validate structure and numbers of both arm chunks."""
    if not isinstance(action, Mapping):
        return {}, [violation("action_format", "Action is not a mapping")]
    parsed: dict[str, Rows] = {}
    findings: list[Finding] = []
    for arm, key in ACTION_KEYS.items():
        if key not in action:
            findings.append(
                violation("action_format", f"Missing required action field: {key}", arm=arm)
            )
            continue
        try:
            parsed[arm] = _as_rows(action[key], key)
        except ValueError as exc:
            findings.append(violation("action_format", str(exc), arm=arm))
    return parsed, findings


def parse_current_state(
    current_joints: Mapping[str, Any] | None, *, required: bool
) -> tuple[dict[str, list[float]], list[Finding]]:
    """Validate the measured joint state of each arm."""
    current: dict[str, list[float]] = {}
    findings: list[Finding] = []
    for arm in ARMS:
        raw_state = current_joints.get(arm) if current_joints else None
        if raw_state is None:
            if required:
                findings.append(
                    violation(
                        "current_state",
                        f"Current {arm} joint state is required but missing",
                        arm=arm,
                    )
                )
            continue
        try:
            current[arm] = _as_vector(
                raw_state, JOINTS_PER_ARM, f"Current {arm} joint state", "6 joints"
            )
        except ValueError as exc:
            findings.append(violation("current_state", str(exc), arm=arm))
    return current, findings


# --- Chunk shape -------------------------------------------------------------------------


def check_chunk_shape(parsed: Mapping[str, Rows], min_rows: int, max_rows: int) -> list[Finding]:
    lengths = {arm: len(rows) for arm, rows in parsed.items()}
    if len(set(lengths.values())) > 1:
        return [
            violation(
                "chunk_shape",
                f"Arm chunks have different lengths: right={lengths.get('right')}, "
                f"left={lengths.get('left')} rows",
            )
        ]
    rows = next(iter(lengths.values()), 0)
    if not min_rows <= rows <= max_rows:
        return [
            violation(
                "chunk_shape",
                f"Chunk has {rows} rows; allowed range is [{min_rows}, {max_rows}] rows",
                value=float(rows),
            )
        ]
    return []


# --- Joint, gripper and motion checks ----------------------------------------------------


def check_joint_limits(
    arm: str, rows: Rows, limits: JointLimits, near_limit_margin: float = 0.0
) -> list[Finding]:
    """Block targets outside limits; warn once per joint when targets come within the margin."""
    findings: list[Finding] = []
    closest: dict[int, tuple[float, int, float, float]] = {}
    for row_index, row in enumerate(rows):
        for joint, (value, (low, high)) in enumerate(zip(row[:JOINTS_PER_ARM], limits)):
            if not low <= value <= high:
                bound = low if value < low else high
                findings.append(
                    violation(
                        "joint_limit",
                        f"{arm} row {row_index}: joint {joint} target {value:.3f} "
                        f"outside [{low:.3f}, {high:.3f}] rad",
                        arm=arm, row=row_index, joint=joint, value=value, limit=bound,
                    )
                )
                continue
            distance, bound = min((value - low, low), (high - value, high))
            if distance < near_limit_margin and (
                joint not in closest or distance < closest[joint][0]
            ):
                closest[joint] = (distance, row_index, value, bound)

    for joint, (distance, row_index, value, bound) in sorted(closest.items()):
        proximity = 1.0 - distance / near_limit_margin
        findings.append(
            warning(
                "joint_limit",
                f"{arm} joint {joint} comes within {distance:.3f} rad of its limit "
                f"{bound:.3f} rad (row {row_index})",
                weight=round(MAX_WARNING_RISK * proximity),
                arm=arm, row=row_index, joint=joint, value=value, limit=bound,
            )
        )
    return findings


def check_gripper(arm: str, rows: Rows, gripper_range: tuple[float, float]) -> list[Finding]:
    low, high = gripper_range
    return [
        violation(
            "gripper",
            f"{arm} row {row_index}: gripper {row[JOINTS_PER_ARM]:.3f} "
            f"outside [{low:g}, {high:g}]",
            arm=arm, row=row_index, value=row[JOINTS_PER_ARM],
            limit=low if row[JOINTS_PER_ARM] < low else high,
        )
        for row_index, row in enumerate(rows)
        if not low <= row[JOINTS_PER_ARM] <= high
    ]


def check_steps(
    arm: str, rows: Rows, start: Sequence[float] | None, max_step: float
) -> list[Finding]:
    """Largest joint change per row; row 0 is compared against the measured state."""
    findings: list[Finding] = []
    previous = start
    for row_index, row in enumerate(rows):
        joints = row[:JOINTS_PER_ARM]
        if previous is not None:
            steps = [abs(a - b) for a, b in zip(joints, previous)]
            largest = max(steps)
            if largest > max_step:
                findings.append(
                    violation(
                        "step",
                        f"{arm} row {row_index}: joint step {largest:.3f} rad "
                        f"exceeds {max_step:.3f} rad",
                        arm=arm, row=row_index, joint=steps.index(largest),
                        value=largest, limit=max_step,
                    )
                )
        previous = joints
    return findings


def check_velocity(
    arm: str, rows: Rows, max_velocity: Sequence[float], action_hz: float
) -> list[Finding]:
    """Per-joint velocity between consecutive rows, played at ``action_hz`` rows per second.

    Row 0 is covered by the step check instead: its distance from the measured state includes
    network latency and is not a commanded velocity.
    """
    findings: list[Finding] = []
    for row_index in range(1, len(rows)):
        velocities = [
            abs(a - b) * action_hz
            for a, b in zip(rows[row_index][:JOINTS_PER_ARM], rows[row_index - 1][:JOINTS_PER_ARM])
        ]
        ratios = [v / limit for v, limit in zip(velocities, max_velocity)]
        worst = max(range(JOINTS_PER_ARM), key=ratios.__getitem__)
        if ratios[worst] > 1.0:
            findings.append(
                violation(
                    "velocity",
                    f"{arm} row {row_index}: joint {worst} velocity {velocities[worst]:.2f} "
                    f"rad/s exceeds {max_velocity[worst]:.2f} rad/s",
                    arm=arm, row=row_index, joint=worst,
                    value=velocities[worst], limit=max_velocity[worst],
                )
            )
    return findings


# --- Forward kinematics, workspace and separation ---------------------------------------


def compute_end_effectors(
    arm: str, rows: Rows, forward_kinematics: ForwardKinematics
) -> tuple[list[Vector3 | None], list[Finding]]:
    """End-effector position per row; ``None`` where FK failed (reported as a violation)."""
    positions: list[Vector3 | None] = []
    findings: list[Finding] = []
    for row_index, row in enumerate(rows):
        try:
            xyz = tuple(float(v) for v in forward_kinematics(arm, row[:JOINTS_PER_ARM]))
            if len(xyz) != 3 or not all(isfinite(v) for v in xyz):
                raise ValueError("FK must return three finite coordinates")
            positions.append(xyz)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 - fail closed on any FK error
            positions.append(None)
            findings.append(
                violation(
                    "fk", f"{arm} row {row_index}: FK check failed: {exc}", arm=arm, row=row_index
                )
            )
    return positions, findings


def check_workspace(
    arm: str,
    positions: Sequence[Vector3 | None],
    workspace_min: Vector3,
    workspace_max: Vector3,
) -> list[Finding]:
    return [
        violation(
            "workspace",
            f"{arm} row {row_index}: end-effector outside configured workspace",
            arm=arm, row=row_index,
        )
        for row_index, xyz in enumerate(positions)
        if xyz is not None
        and not all(workspace_min[i] <= xyz[i] <= workspace_max[i] for i in range(3))
    ]


def check_separation(
    positions: Mapping[str, Sequence[Vector3 | None]], minimum: float
) -> list[Finding]:
    """Distance between the two end effectors per row (not full-link collision checking)."""
    right, left = positions.get("right"), positions.get("left")
    if right is None or left is None or len(right) != len(left) or None in right or None in left:
        return [violation("separation", "Cannot compare end-effectors: FK results are incomplete")]
    findings: list[Finding] = []
    for row_index, (a, b) in enumerate(zip(right, left)):
        distance = sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))  # type: ignore[index]
        if distance < minimum:
            findings.append(
                violation(
                    "separation",
                    f"Row {row_index}: end-effector separation {distance:.3f} m "
                    f"is below {minimum:.3f} m",
                    row=row_index, value=distance, limit=minimum,
                )
            )
    return findings
