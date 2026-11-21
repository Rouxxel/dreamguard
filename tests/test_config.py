import json

import pytest

from dreamguard import SafetyConfig, SafetyGuard, load_builtin_profile, load_profile

YAM_LIMITS = [
    (-2.61799, 3.05433),
    (0.0, 3.66519),
    (0.0, 3.66519),
    (-1.5708, 1.5708),
    (-1.5708, 1.5708),
    (-2.0944, 2.0944),
]


def test_default_config_is_valid():
    config = SafetyConfig()
    assert config.require_current_state
    assert config.max_joint_velocity_rad_s is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"max_joint_step_rad": float("nan")}, "max_joint_step_rad"),
        ({"max_joint_step_rad": 0.0}, "max_joint_step_rad"),
        ({"action_hz": -20.0}, "action_hz"),
        ({"near_limit_margin_rad": -0.1}, "near_limit_margin_rad"),
        ({"gripper_tolerance": -0.01}, "gripper_tolerance"),
        ({"gripper_tolerance": 0.5}, "gripper_tolerance"),
        ({"gripper_range": (1.0, 0.0)}, "gripper_range"),
        ({"gripper_range": (0.0,)}, "gripper_range"),
        ({"min_rows": 0}, "min_rows"),
        ({"min_rows": 10, "max_rows": 5}, "max_rows"),
        ({"max_rows": True}, "max_rows"),
        ({"workspace_min_m": (0.0, 0.0, 2.0)}, "workspace_min_m"),
        ({"workspace_max_m": (1.0, float("inf"), 1.0)}, "workspace_max_m"),
        ({"minimum_tool_separation_m": -0.1}, "minimum_tool_separation_m"),
        ({"max_joint_velocity_rad_s": (1.0,) * 5}, "max_joint_velocity_rad_s"),
        ({"max_joint_velocity_rad_s": (1.0, 1.0, 1.0, 1.0, 1.0, 0.0)}, "max_joint_velocity"),
        ({"require_current_state": "yes"}, "require_current_state"),
        ({"joint_limits": {"right": YAM_LIMITS}}, "joint_limits.left"),
        ({"joint_limits": {"right": YAM_LIMITS[:5], "left": YAM_LIMITS}}, "joint_limits.right"),
        ({"joint_limits": {"right": [(1.0, -1.0)] * 6, "left": YAM_LIMITS}}, "joint_limits.right"),
    ],
)
def test_invalid_config_is_rejected_at_construction(overrides, message):
    with pytest.raises(ValueError, match=message):
        SafetyConfig(**overrides)


def test_config_normalizes_lists_to_tuples():
    config = SafetyConfig(
        joint_limits={arm: [list(pair) for pair in YAM_LIMITS] for arm in ("right", "left")},
        gripper_range=[0, 1],
        workspace_min_m=[-1, -1, 0],
    )
    assert config.joint_limits["right"][1] == (0.0, 3.66519)
    assert config.gripper_range == (0.0, 1.0)
    assert config.workspace_min_m == (-1.0, -1.0, 0.0)


def test_from_dict_rejects_unknown_keys():
    with pytest.raises(ValueError, match="max_joint_stepp_rad"):
        SafetyConfig.from_dict({"max_joint_stepp_rad": 0.1})


def test_from_dict_accepts_metadata_keys():
    config = SafetyConfig.from_dict({"name": "x", "description": "y", "notes": [], "min_rows": 2})
    assert config.min_rows == 2


def test_from_dict_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        SafetyConfig.from_dict([1, 2, 3])


def test_load_profile_from_file(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"name": "custom", "max_joint_step_rad": 0.2}), encoding="utf-8")
    assert load_profile(path).max_joint_step_rad == 0.2


def test_builtin_yam_profile_uses_menagerie_joint_ranges():
    config = load_builtin_profile("yam_sim")
    assert list(config.joint_limits["right"]) == YAM_LIMITS
    assert list(config.joint_limits["left"]) == YAM_LIMITS
    assert config.action_hz == 20.0
    assert config.max_joint_velocity_rad_s == (3.0,) * 6
    assert config.gripper_tolerance == 0.02
    assert config.require_current_state


def test_unknown_builtin_profile_is_rejected():
    with pytest.raises(ValueError, match="Unknown built-in"):
        load_builtin_profile("does_not_exist")


def test_yam_profile_blocks_target_outside_real_joint_range():
    guard = SafetyGuard(load_builtin_profile("yam_sim"))
    home = [0.0, 0.1, 0.1, 0.0, 0.0, 0.0]
    below_joint2 = [0.0, -0.2, 0.1, 0.0, 0.0, 0.0, 0.5]
    report = guard.inspect(
        {"q_r_chunk": [below_joint2], "q_l_chunk": [home + [0.5]]},
        current_joints={"right": home, "left": home},
    )
    assert not report.approved
    assert any(f.check == "joint_limit" and f.joint == 1 for f in report.violations)
