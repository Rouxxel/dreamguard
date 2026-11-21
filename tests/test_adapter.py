import numpy as np
import pytest

from dreamguard import Decision, SafetyGuard, UnsafeActionError
from dreamguard.adapter import (
    ControllerHaltedError,
    GuardedController,
    current_joints_from_observation,
    guarded_get_action,
)
from dreamguard.events import EventBus

HOME = [0.0] * 6
CURRENT = {"right": HOME, "left": HOME}
SAFE_ROW = HOME + [0.5]


class SpyRobot:
    def __init__(self, fail_with: Exception | None = None):
        self.played: list[dict] = []
        self.fail_with = fail_with

    def play(self, action):
        if self.fail_with is not None:
            raise self.fail_with
        self.played.append(action)


class FakeClient:
    def __init__(self, action):
        self.action = action

    def get_action(self):
        return self.action


def safe_action():
    return {"q_r_chunk": [list(SAFE_ROW)], "q_l_chunk": [list(SAFE_ROW)], "per_key": {"x": 1}}


def unsafe_actions():
    nan_row = [float("nan")] + HOME[1:] + [0.5]
    over_limit = [4.0] + HOME[1:] + [0.5]
    return {
        "nan": {"q_r_chunk": [nan_row], "q_l_chunk": [list(SAFE_ROW)]},
        "joint_limit": {"q_r_chunk": [over_limit], "q_l_chunk": [list(SAFE_ROW)]},
        "missing_arm": {"q_r_chunk": [list(SAFE_ROW)]},
        "mismatched_lengths": {"q_r_chunk": [list(SAFE_ROW)] * 3, "q_l_chunk": [list(SAFE_ROW)]},
        "gripper": {"q_r_chunk": [HOME + [1.5]], "q_l_chunk": [list(SAFE_ROW)]},
        "not_a_mapping": [SAFE_ROW],
    }


def make_controller(robot=None, **kwargs):
    robot = robot or SpyRobot()
    return robot, GuardedController(robot, SafetyGuard(), **kwargs)


# --- Interception ---------------------------------------------------------------------


def test_approved_action_is_played_once_with_metadata():
    robot, controller = make_controller()
    report = controller.submit(safe_action(), current_joints=CURRENT)
    assert report.decision is Decision.APPROVE
    assert len(robot.played) == 1
    assert robot.played[0]["per_key"] == {"x": 1}


def test_played_action_is_a_copy_of_the_validated_action():
    robot, controller = make_controller()
    action = safe_action()
    controller.submit(action, current_joints=CURRENT)
    action["q_r_chunk"][0][0] = 99.0
    assert robot.played[0]["q_r_chunk"][0][0] == 0.0


@pytest.mark.parametrize("name", list(unsafe_actions()))
def test_blocked_actions_never_reach_the_robot(name):
    robot, controller = make_controller(max_consecutive_blocks=10)
    report = controller.submit(unsafe_actions()[name], current_joints=CURRENT)
    assert report.decision is Decision.BLOCK
    assert robot.played == []


def test_missing_current_state_blocks_and_never_plays():
    robot, controller = make_controller()
    assert not controller.submit(safe_action()).approved
    assert robot.played == []


def test_current_state_is_taken_from_observation():
    robot, controller = make_controller()
    observation = {
        "state.right_arm": np.zeros(6, dtype=np.float32),
        "state.left_arm": np.zeros(6, dtype=np.float32),
        "prompt": "fold the towel",
    }
    assert controller.submit(safe_action(), observation=observation).approved
    assert len(robot.played) == 1


def test_on_block_hook_receives_the_report():
    seen = []
    _robot, controller = make_controller(on_block=seen.append)
    controller.submit(unsafe_actions()["gripper"], current_joints=CURRENT)
    assert len(seen) == 1
    assert seen[0].decision is Decision.BLOCK


# --- Halting -----------------------------------------------------------------------------


def test_controller_halts_after_consecutive_blocks_and_refuses_actions():
    robot, controller = make_controller(max_consecutive_blocks=2)
    bad = unsafe_actions()["joint_limit"]
    controller.submit(bad, current_joints=CURRENT)
    assert not controller.halted
    controller.submit(bad, current_joints=CURRENT)
    assert controller.halted
    with pytest.raises(ControllerHaltedError):
        controller.submit(safe_action(), current_joints=CURRENT)
    assert robot.played == []


def test_reset_clears_halt():
    robot, controller = make_controller(max_consecutive_blocks=1)
    controller.submit(unsafe_actions()["joint_limit"], current_joints=CURRENT)
    controller.reset()
    assert controller.submit(safe_action(), current_joints=CURRENT).approved
    assert len(robot.played) == 1


def test_approval_resets_consecutive_block_counter():
    _robot, controller = make_controller(max_consecutive_blocks=2)
    bad = unsafe_actions()["joint_limit"]
    controller.submit(bad, current_joints=CURRENT)
    controller.submit(safe_action(), current_joints=CURRENT)
    controller.submit(bad, current_joints=CURRENT)
    assert not controller.halted


def test_invalid_block_threshold_is_rejected():
    with pytest.raises(ValueError):
        GuardedController(SpyRobot(), SafetyGuard(), max_consecutive_blocks=0)


# --- Events ------------------------------------------------------------------------------


def test_every_submission_publishes_an_event():
    bus = EventBus()
    events = []
    bus.subscribe(events.append)
    _, controller = make_controller(bus=bus, session_id="test-session", source="unit")
    controller.submit(safe_action(), current_joints=CURRENT)
    controller.submit(unsafe_actions()["nan"], current_joints=CURRENT)

    assert [e.sequence for e in events] == [1, 2]
    assert [e.executed for e in events] == [True, False]
    assert [e.report.decision for e in events] == [Decision.APPROVE, Decision.BLOCK]
    assert all(e.session_id == "test-session" and e.source == "unit" for e in events)


def test_halt_is_recorded_in_the_event():
    bus = EventBus()
    events = []
    bus.subscribe(events.append)
    _, controller = make_controller(bus=bus, max_consecutive_blocks=1)
    controller.submit(unsafe_actions()["gripper"], current_joints=CURRENT)
    assert events[-1].halted


def test_robot_failure_is_recorded_and_propagated():
    bus = EventBus()
    events = []
    bus.subscribe(events.append)
    robot = SpyRobot(fail_with=RuntimeError("motor fault"))
    _, controller = make_controller(robot, bus=bus)
    with pytest.raises(RuntimeError, match="motor fault"):
        controller.submit(safe_action(), current_joints=CURRENT)
    assert events[-1].executed is False
    assert "motor fault" in events[-1].error


def test_failing_subscriber_does_not_stop_execution():
    bus = EventBus()

    def broken(event):
        raise RuntimeError("dashboard disconnected")

    bus.subscribe(broken)
    robot, controller = make_controller(bus=bus)
    assert controller.submit(safe_action(), current_joints=CURRENT).approved
    assert len(robot.played) == 1


def test_invalid_session_id_is_rejected():
    with pytest.raises(ValueError):
        GuardedController(SpyRobot(), SafetyGuard(), session_id="../escape")


# --- guarded_get_action -------------------------------------------------------------------


def test_guarded_get_action_uses_observation_state():
    observation = {"state.right_arm": HOME, "state.left_arm": HOME}
    action = guarded_get_action(FakeClient(safe_action()), SafetyGuard(), observation)
    assert action["q_r_chunk"] == [SAFE_ROW]


def test_guarded_get_action_raises_for_unsafe_action():
    with pytest.raises(UnsafeActionError):
        guarded_get_action(
            FakeClient(unsafe_actions()["nan"]), SafetyGuard(), current_joints=CURRENT
        )


def test_guarded_get_action_without_state_fails_closed():
    with pytest.raises(UnsafeActionError):
        guarded_get_action(FakeClient(safe_action()), SafetyGuard())


def test_current_joints_from_observation_skips_missing_arms():
    assert current_joints_from_observation({"state.right_arm": HOME}) == {"right": HOME}
