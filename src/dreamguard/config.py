"""Safety configuration, validation and JSON safety profiles."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields
from importlib import resources
from math import isfinite
from numbers import Real
from pathlib import Path
from typing import Any

Vector3 = tuple[float, float, float]
JointLimits = tuple[tuple[float, float], ...]

ARMS = ("right", "left")
JOINTS_PER_ARM = 6
PROFILE_METADATA_KEYS = frozenset({"name", "description", "source", "notes"})


def _default_joint_limits() -> dict[str, JointLimits]:
    return {arm: ((-3.14159, 3.14159),) * JOINTS_PER_ARM for arm in ARMS}


@dataclass(frozen=True)
class SafetyConfig:
    """Development guardrails; calibrate these against the simulator embodiment.

    Construction fails with ``ValueError`` when any value is missing, non-finite or
    inconsistent, so a guard can never run with an unusable configuration.
    """

    joint_limits: Mapping[str, JointLimits] = field(default_factory=_default_joint_limits)
    gripper_range: tuple[float, float] = (0.0, 1.0)
    max_joint_step_rad: float = 0.35
    max_joint_velocity_rad_s: tuple[float, ...] | None = None
    action_hz: float = 20.0
    near_limit_margin_rad: float = 0.0
    require_current_state: bool = True
    min_rows: int = 1
    max_rows: int = 200
    require_workspace_check: bool = False
    workspace_min_m: Vector3 = (-1.0, -1.0, 0.0)
    workspace_max_m: Vector3 = (1.0, 1.0, 1.5)
    minimum_tool_separation_m: float | None = None

    def __post_init__(self) -> None:
        errors: list[str] = []
        normalized = {
            "joint_limits": _normalize_joint_limits(self.joint_limits, errors),
            "gripper_range": _normalize_range(self.gripper_range, "gripper_range", errors),
            "max_joint_velocity_rad_s": _normalize_velocity(self.max_joint_velocity_rad_s, errors),
            "workspace_min_m": _normalize_vector3(self.workspace_min_m, "workspace_min_m", errors),
            "workspace_max_m": _normalize_vector3(self.workspace_max_m, "workspace_max_m", errors),
        }
        _require_positive(self.max_joint_step_rad, "max_joint_step_rad", errors)
        _require_positive(self.action_hz, "action_hz", errors)
        if not _is_number(self.near_limit_margin_rad) or self.near_limit_margin_rad < 0:
            errors.append("near_limit_margin_rad must be a finite number >= 0")
        if self.minimum_tool_separation_m is not None:
            _require_positive(self.minimum_tool_separation_m, "minimum_tool_separation_m", errors)
        for name in ("require_current_state", "require_workspace_check"):
            if not isinstance(getattr(self, name), bool):
                errors.append(f"{name} must be true or false")
        if not _is_int(self.min_rows) or self.min_rows < 1:
            errors.append("min_rows must be an integer >= 1")
        elif not _is_int(self.max_rows) or self.max_rows < self.min_rows:
            errors.append("max_rows must be an integer >= min_rows")
        workspace_min, workspace_max = normalized["workspace_min_m"], normalized["workspace_max_m"]
        if workspace_min and workspace_max and any(
            low >= high for low, high in zip(workspace_min, workspace_max)
        ):
            errors.append("workspace_min_m must be below workspace_max_m on every axis")

        if errors:
            raise ValueError("Invalid safety configuration: " + "; ".join(errors))
        for name, value in normalized.items():
            object.__setattr__(self, name, value)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SafetyConfig:
        """Build a configuration from a profile mapping; unknown keys are rejected."""
        if not isinstance(data, Mapping):
            raise ValueError("Safety profile must be a JSON object")  # noqa: TRY004
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known - PROFILE_METADATA_KEYS
        if unknown:
            raise ValueError(f"Unknown safety profile keys: {', '.join(sorted(unknown))}")
        return cls(**{key: value for key, value in data.items() if key in known})


def load_profile(path: str | Path) -> SafetyConfig:
    """Load a JSON safety profile from disk."""
    with Path(path).open(encoding="utf-8") as file:
        return SafetyConfig.from_dict(json.load(file))


def load_builtin_profile(name: str) -> SafetyConfig:
    """Load a profile shipped with DreamGuard (``dreamguard/profiles/<name>.json``)."""
    profile = resources.files("dreamguard") / "profiles" / f"{name}.json"
    if not profile.is_file():
        raise ValueError(f"Unknown built-in safety profile: {name}")
    return SafetyConfig.from_dict(json.loads(profile.read_text(encoding="utf-8")))


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(float(value))


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_positive(value: Any, name: str, errors: list[str]) -> None:
    if not _is_number(value) or value <= 0:
        errors.append(f"{name} must be a finite number > 0")


def _as_sequence(value: Any) -> Sequence[Any] | None:
    return value if isinstance(value, (list, tuple)) else None


def _normalize_range(value: Any, name: str, errors: list[str]) -> tuple[float, float] | None:
    pair = _as_sequence(value)
    if pair is None or len(pair) != 2 or not all(_is_number(v) for v in pair):
        errors.append(f"{name} must be two finite numbers")
        return None
    low, high = float(pair[0]), float(pair[1])
    if low >= high:
        errors.append(f"{name} lower bound must be below its upper bound")
        return None
    return (low, high)


def _normalize_joint_limits(value: Any, errors: list[str]) -> dict[str, JointLimits]:
    if not isinstance(value, Mapping):
        errors.append("joint_limits must map each arm to six [low, high] pairs")
        return {}
    normalized: dict[str, JointLimits] = {}
    for arm in ARMS:
        limits = _as_sequence(value.get(arm))
        if limits is None or len(limits) != JOINTS_PER_ARM:
            errors.append(f"joint_limits.{arm} must contain {JOINTS_PER_ARM} [low, high] pairs")
            continue
        pairs = [
            _normalize_range(pair, f"joint_limits.{arm}[{index}]", errors)
            for index, pair in enumerate(limits)
        ]
        if all(pair is not None for pair in pairs):
            normalized[arm] = tuple(pairs)  # type: ignore[arg-type]
    return normalized


def _normalize_velocity(value: Any, errors: list[str]) -> tuple[float, ...] | None:
    if value is None:
        return None
    limits = _as_sequence(value)
    if limits is None or len(limits) != JOINTS_PER_ARM or not all(
        _is_number(v) and v > 0 for v in limits
    ):
        errors.append(
            f"max_joint_velocity_rad_s must be null or {JOINTS_PER_ARM} finite numbers > 0"
        )
        return None
    return tuple(float(v) for v in limits)


def _normalize_vector3(value: Any, name: str, errors: list[str]) -> Vector3 | None:
    vector = _as_sequence(value)
    if vector is None or len(vector) != 3 or not all(_is_number(v) for v in vector):
        errors.append(f"{name} must be three finite numbers")
        return None
    return (float(vector[0]), float(vector[1]), float(vector[2]))
