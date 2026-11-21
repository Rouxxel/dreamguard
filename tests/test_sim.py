import base64
import io

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")
pytest.importorskip("PIL")

from PIL import Image

from dreamguard import Decision, SafetyGuard, load_builtin_profile
from dreamguard.adapter import GuardedController
from dreamguard.events import EventBus, JsonlSessionRecorder
from dreamguard.sim import CAMERAS, SimKinematics, SimRobot, build_model, run_loop
from dreamguard.sim.scene import HOME_JOINTS
from dreamguard.sources import FAULTS, FakeDreamClient, ReplayDreamClient
from dreamguard.sources.fake import FakeClientError
from dreamguard.sources.replay import ReplayExhaustedError


@pytest.fixture(scope="module")
def model():
    return build_model()


@pytest.fixture()
def robot(model):
    sim = SimRobot(model)
    yield sim
    sim.close()


@pytest.fixture()
def guard(model):
    return SafetyGuard(load_builtin_profile("yam_sim"), forward_kinematics=SimKinematics(model))


@pytest.fixture()
def client():
    fake = FakeDreamClient()
    fake.policy({"checkpoint": "offline"})
    return fake


def chunk_from(robot, target, rows=30, gripper=1.0):
    rows_out = []
    for arm in ("right", "left"):
        start = robot.joints(arm)
        ramp = [list(start + (np.array(target) - start) * (i + 1) / rows) + [gripper]
                for i in range(rows)]
        rows_out.append(ramp)
    return {"q_r_chunk": rows_out[0], "q_l_chunk": rows_out[1]}


def renderer_available(model):
    try:
        mujoco.Renderer(model, 32, 32).close()
    except Exception:  # noqa: BLE001 - no OpenGL backend on this machine
        return False
    return True


# --- Scene -------------------------------------------------------------------------------


def test_scene_has_two_arms_and_three_cameras(model):
    assert model.nu == 14
    assert {model.camera(i).name for i in range(model.ncam)} == set(CAMERAS.values())
    for arm in ("right", "left"):
        assert model.site(f"{arm}_grasp_site").id >= 0


# --- Robot state and control ---------------------------------------------------------------


def test_reset_puts_both_arms_at_home(robot):
    for arm in ("right", "left"):
        np.testing.assert_allclose(robot.joints(arm), HOME_JOINTS, atol=1e-6)
        assert robot.gripper(arm)[0] == pytest.approx(1.0, abs=0.05)


def test_observation_matches_dream1_keys_and_dtypes(robot):
    observation = robot.observation("fold the towel")
    assert observation["prompt"] == "fold the towel"
    for arm in ("right", "left"):
        assert observation[f"state.{arm}_arm"].dtype == np.float32
        assert observation[f"state.{arm}_arm"].shape == (6,)
        assert observation[f"state.{arm}_gripper"].shape == (1,)


def test_play_tracks_targets_and_respects_execution_horizon(robot):
    target = [0.2, 1.4, 1.2, 0.1, 0.2, 0.0]
    played = robot.play(chunk_from(robot, target, rows=40))
    assert played == robot.execution_horizon == 30
    robot.hold(1.0)
    assert np.max(np.abs(robot.joints("right") - np.array(target) * 0.75 - np.array(
        HOME_JOINTS) * 0.25)) < 0.05


def test_gripper_command_closes_fingers(robot):
    robot.play(chunk_from(robot, HOME_JOINTS, rows=20, gripper=0.0))
    robot.hold(1.0)
    assert robot.gripper("right")[0] < 0.1


def test_hold_keeps_the_last_targets(robot):
    before = robot.joints("left").copy()
    robot.hold(2.0)
    np.testing.assert_allclose(robot.joints("left"), before, atol=1e-3)


def test_interrupt_stops_playback(robot):
    robot.interrupt()
    assert robot.play(chunk_from(robot, HOME_JOINTS)) == 0
    robot.clear_interrupt()
    assert robot.play(chunk_from(robot, HOME_JOINTS)) == 30


def test_frames_are_base64_jpegs_of_the_dream1_size(robot, model):
    if not renderer_available(model):
        pytest.skip("No OpenGL rendering backend available")
    frames = robot.frames()
    assert set(frames) == {"video.overhead", "video.wrist_l", "video.wrist_r"}
    image = Image.open(io.BytesIO(base64.b64decode(frames["video.overhead"])))
    assert image.format == "JPEG"
    assert image.size == (320, 176)


# --- Kinematics ---------------------------------------------------------------------------


def test_fk_at_home_is_in_front_of_each_base(model):
    fk = SimKinematics(model)
    assert fk("right", HOME_JOINTS) == pytest.approx((0.377, -0.3, 1.143), abs=0.002)
    assert fk("left", HOME_JOINTS) == pytest.approx((0.377, 0.3, 1.143), abs=0.002)


def test_fk_matches_simulation_and_does_not_disturb_it(robot, model):
    target = [0.2, 1.4, 1.2, 0.1, 0.2, 0.0]
    robot.play(chunk_from(robot, target))
    robot.hold(1.0)
    before = robot.joints("right").copy()
    xyz = SimKinematics(model)("right", robot.joints("right"))
    np.testing.assert_allclose(xyz, robot.data.site("right_grasp_site").xpos, atol=1e-4)
    np.testing.assert_array_equal(robot.joints("right"), before)


def test_fk_rejects_bad_input(model):
    fk = SimKinematics(model)
    with pytest.raises(ValueError):
        fk("middle", HOME_JOINTS)
    with pytest.raises(ValueError):
        fk("right", HOME_JOINTS[:5])


# --- Fake Dream-1 client ------------------------------------------------------------------


def test_fake_client_requires_policy_and_observation():
    fake = FakeDreamClient()
    with pytest.raises(FakeClientError):
        fake.get_action()
    fake.policy({})
    with pytest.raises(FakeClientError):
        fake.get_action()


def test_fake_chunks_start_at_measured_state_and_stay_slow(robot, client):
    client.set_observation({}, robot.observation())
    action = client.get_action()
    for key, arm in (("q_r_chunk", "right"), ("q_l_chunk", "left")):
        rows = np.array(action[key])
        assert rows.shape == (50, 7)
        assert np.max(np.abs(rows[0, :6] - robot.joints(arm))) <= client.max_step + 1e-6
        assert np.max(np.abs(np.diff(rows[:, :6], axis=0))) <= client.max_step + 1e-6


def test_unknown_fault_is_rejected(client):
    with pytest.raises(ValueError, match="Unknown fault"):
        client.inject("teleport")


def test_scripted_run_is_approved_end_to_end(robot, guard, client):
    controller = GuardedController(robot, guard)
    result = run_loop(client, robot, controller, chunks=10, render_frames=False)
    assert [r.decision for r in result.reports] == [Decision.APPROVE] * 10
    assert client.waypoint_index != 0 or client.calls > 5
    assert robot.rows_played == 300


@pytest.mark.parametrize(
    ("fault", "check"),
    [
        ("joint_limit", "joint_limit"),
        ("big_step", "step"),
        ("velocity", "velocity"),
        ("nan", "action_format"),
        ("gripper", "gripper"),
        ("missing_arm", "action_format"),
        ("mismatched_lengths", "chunk_shape"),
        ("workspace", "workspace"),
        ("separation", "separation"),
    ],
)
def test_each_fault_is_blocked_by_its_check_and_never_played(robot, guard, client, fault, check):
    controller = GuardedController(robot, guard)
    run_loop(client, robot, controller, chunks=1, render_frames=False)
    rows_before = robot.rows_played
    client.inject(fault)
    report = run_loop(client, robot, controller, chunks=1, render_frames=False).reports[0]
    assert report.decision is Decision.BLOCK
    assert {f.check for f in report.violations} == {check}
    assert robot.rows_played == rows_before


def test_fault_catalogue_is_fully_covered():
    assert len(FAULTS) == 9


def test_faults_are_one_shot(robot, guard, client):
    controller = GuardedController(robot, guard)
    client.inject("gripper")
    reports = run_loop(client, robot, controller, chunks=2, render_frames=False).reports
    assert [r.decision for r in reports] == [Decision.BLOCK, Decision.APPROVE]


def test_repeated_faults_halt_the_loop(robot, guard, client):
    controller = GuardedController(robot, guard, max_consecutive_blocks=2)
    result = run_loop(
        client, robot, controller, chunks=5, render_frames=False,
        before_chunk=lambda _: client.inject("nan"),
    )
    assert result.halted
    assert len(result.reports) == 2
    assert robot.rows_played == 0


# --- Replay -------------------------------------------------------------------------------


def test_recorded_session_replays_through_the_guard(robot, guard, client, model, tmp_path):
    bus = EventBus()
    recorder = JsonlSessionRecorder(tmp_path)
    bus.subscribe(recorder)
    controller = GuardedController(robot, guard, bus=bus, session_id="recorded")
    run_loop(client, robot, controller, chunks=3, render_frames=False)

    replay = ReplayDreamClient.from_file(recorder.path_for("recorded"))
    assert len(replay) == 3
    fresh = SimRobot(model)
    result = run_loop(replay, fresh, GuardedController(fresh, guard), chunks=5, render_frames=False)
    assert result.exhausted
    assert [r.decision for r in result.reports] == [Decision.APPROVE] * 3


def test_replay_exhaustion_and_loop():
    action = {"q_r_chunk": [[0.0] * 7], "q_l_chunk": [[0.0] * 7]}
    replay = ReplayDreamClient([action])
    replay.get_action()
    with pytest.raises(ReplayExhaustedError):
        replay.get_action()
    looping = ReplayDreamClient([action], loop=True)
    assert looping.get_action() == looping.get_action()


def test_replay_returns_independent_copies():
    replay = ReplayDreamClient([{"q_r_chunk": [[0.0] * 7], "q_l_chunk": [[0.0] * 7]}], loop=True)
    replay.get_action()["q_r_chunk"][0][0] = 9.0
    assert replay.get_action()["q_r_chunk"][0][0] == 0.0
