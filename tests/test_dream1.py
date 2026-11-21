import json
import socket

import pytest

from dreamguard.events import read_session
from dreamguard.sources import ReplayDreamClient, dream1
from dreamguard.sources.dream1 import (
    Dream1Source,
    PaidCallBudgetExhausted,
    check_inputs,
    policy_config,
    preflight,
)

SAFE_ROW = [0.0, 1.047, 1.047, 0.0, 0.0, 0.0, 1.0]


class FakeSdkClient:
    """Stands in for dream.DreamClient; records calls, never touches the network."""

    def __init__(self, fail_with=None):
        self.policies, self.observations, self.actions_sent = [], [], 0
        self.closed = False
        self.fail_with = fail_with
        self.last_timing = {"total_ms": 420.0}

    def policy(self, config):
        self.policies.append(config)

    def set_observation(self, frames, observation, *, timestamp=None):
        self.observations.append((frames, observation))

    def get_action(self, *, commanded=None):
        self.actions_sent += 1
        if self.fail_with:
            raise self.fail_with
        return {"q_r_chunk": [list(SAFE_ROW)] * 3, "q_l_chunk": [list(SAFE_ROW)] * 3, "per_key": {}}

    def close(self):
        self.closed = True


OBSERVATION = {
    "state.right_arm": [0.0, 1.047, 1.047, 0.0, 0.0, 0.0],
    "state.right_gripper": [1.0],
    "state.left_arm": [0.0, 1.047, 1.047, 0.0, 0.0, 0.0],
    "state.left_gripper": [1.0],
    "prompt": "tidy up",
}


def make_source(tmp_path=None, max_calls=2, fake=None):
    fake = fake or FakeSdkClient()
    source = Dream1Source(
        max_calls=max_calls,
        fixtures_dir=tmp_path,
        session_id="live-test",
        client_factory=lambda: fake,
    )
    source.policy()
    source.set_observation({"video.overhead": "x"}, OBSERVATION)
    return source, fake


def test_policy_config_disables_recording_and_carries_embodiment():
    config = policy_config()
    assert config["_record"] is False
    assert config["checkpoint"] == "dreamlabs/dream-1-beta"
    assert set(config["embodiment"]) == {"state", "action", "video"}
    assert config["ik"] == {"arm": "yam", "head": "joint"}


def test_unsafe_configs_are_refused():
    with pytest.raises(ValueError, match="_record"):
        Dream1Source(max_calls=1, config={**policy_config(), "_record": True})
    with pytest.raises(ValueError, match="embodiment"):
        config = policy_config()
        del config["embodiment"]
        Dream1Source(max_calls=1, config=config)
    with pytest.raises(ValueError, match="max_calls"):
        Dream1Source(max_calls=0)


def test_policy_always_uses_the_safe_config():
    source, fake = make_source()
    source.policy({"checkpoint": "something-else", "_record": True})
    assert all(p["_record"] is False for p in fake.policies)
    assert fake.policies[-1]["checkpoint"] == "dreamlabs/dream-1-beta"


def test_budget_caps_paid_calls_before_sending():
    source, fake = make_source(max_calls=2)
    source.get_action()
    source.get_action()
    with pytest.raises(PaidCallBudgetExhausted):
        source.get_action()
    assert fake.actions_sent == 2
    assert source.calls == 2
    assert source.remaining_calls == 0


def test_failed_calls_count_against_the_budget(tmp_path):
    failing = FakeSdkClient(RuntimeError("DA-2000"))
    source, _ = make_source(tmp_path, max_calls=1, fake=failing)
    with pytest.raises(RuntimeError):
        source.get_action()
    with pytest.raises(PaidCallBudgetExhausted):
        source.get_action()
    [line] = read_session(source.fixture_path)
    assert line["error"] == "RuntimeError: DA-2000"
    assert line["action"] is None


def test_replies_are_recorded_and_replayable(tmp_path):
    source, _ = make_source(tmp_path)
    source.get_action()
    [line] = read_session(source.fixture_path)
    assert line["sequence"] == 1
    assert line["observation_state"]["state.right_arm"][1] == 1.047
    assert "video.overhead" not in json.dumps(line)  # frames are never stored
    assert line["timing"] == {"total_ms": 420.0}
    replay = ReplayDreamClient.from_file(source.fixture_path)
    assert replay.get_action()["q_r_chunk"][0] == SAFE_ROW


def test_close_closes_the_sdk_client():
    source, fake = make_source()
    source.close()
    assert fake.closed


def test_default_factory_is_replaceable(monkeypatch):
    fake = FakeSdkClient()
    monkeypatch.setattr(dream1, "CLIENT_FACTORY", lambda: fake)
    source = Dream1Source(max_calls=1)
    source.policy()
    assert fake.policies


# --- Preflight ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def robot():
    pytest.importorskip("mujoco")
    from dreamguard.sim import SimRobot

    sim = SimRobot()
    try:
        sim.render("overhead")
    except Exception:  # noqa: BLE001 - no OpenGL backend
        pytest.skip("No OpenGL rendering backend available")
    yield sim
    sim.close()


def test_offline_inputs_match_the_dream1_yam_contract(robot):
    result = check_inputs(robot, "tidy up")
    assert result["ok"], result["problems"]
    assert result["recording_to_dream_labs"] is False
    assert result["frames"]["video.wrist_l"] == {"format": "JPEG", "width": 320, "height": 176}
    assert result["state"]["state.left_gripper"] == {"shape": [1], "dtype": "float32"}


def test_level1_preflight_never_creates_an_sdk_client(robot):
    def forbidden():
        raise AssertionError("SDK client must not be created")

    result = preflight(robot, client_factory=forbidden)
    assert result["model_lookup"] == "skipped"


def test_level2_preflight_opens_policy_but_never_calls_get_action(robot):
    fake = FakeSdkClient()
    result = preflight(
        robot, prompt="tidy up", allow_model_lookup=True, client_factory=lambda: fake
    )
    assert result["paid_calls_made"] == 0
    assert fake.actions_sent == 0
    assert len(fake.policies) == 1
    frames, observation = fake.observations[0]
    assert set(frames) == {"video.overhead", "video.wrist_l", "video.wrist_r"}
    assert observation["prompt"] == "tidy up"
    assert fake.closed


def test_network_guard_blocks_external_connections():
    with pytest.raises(AssertionError, match="external network"):
        socket.create_connection(("203.0.113.1", 443), timeout=1)
