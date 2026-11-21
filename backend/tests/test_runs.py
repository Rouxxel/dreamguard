import pytest
from conftest import wait_for

FINISHED = ("completed", "stopped", "error")


def current(client):
    return client.get("/api/runs/current").json()


def finish(client):
    return wait_for(lambda: current(client)["state"] in FINISHED and current(client))


def test_idle_before_any_run(client):
    assert current(client)["state"] == "idle"


def test_catalog_lists_sources_faults_and_cameras(client):
    catalog = client.get("/api/runs/catalog").json()
    assert set(catalog["sources"]) == {"fake", "replay", "dream1"}
    assert catalog["sources"]["dream1"]["paid"] is True
    assert len(catalog["faults"]) == 9
    assert catalog["faults"]["workspace"]["expected_check"] == "workspace"
    assert catalog["faults"]["workspace"]["description"]
    assert set(catalog["cameras"]) == {"overhead", "wrist_l", "wrist_r"}
    assert catalog["paid_calls_allowed"] is False


def test_scripted_run_completes_with_every_chunk_approved(client):
    response = client.post("/api/runs", json={"source": "fake", "max_chunks": 5})
    assert response.status_code == 201
    run_id = response.json()["run_id"]

    status = finish(client)
    assert status["run_id"] == run_id
    assert status["state"] == "completed"
    assert status["chunks"] == 5
    assert status["rows_played"] == 150

    summary = client.get("/api/safety/metrics").json()["summary"]
    assert summary["actions_evaluated"] == 5
    assert summary["approved"] == 5
    assert summary["false_rejections"] == 0


def test_only_one_run_at_a_time(client):
    run_id = client.post("/api/runs", json={"source": "fake"}).json()["run_id"]
    assert client.post("/api/runs", json={"source": "fake"}).status_code == 409
    assert client.post(f"/api/runs/{run_id}/stop").json()["state"] == "stopped"


def test_injected_fault_is_blocked_and_counted(client):
    run_id = client.post("/api/runs", json={"source": "fake"}).json()["run_id"]
    response = client.post(f"/api/runs/{run_id}/faults", json={"fault": "joint_limit"})
    assert response.status_code == 202
    assert response.json()["description"]

    wait_for(lambda: client.get("/api/safety/metrics").json()["summary"]["unsafe_injected"])
    client.post(f"/api/runs/{run_id}/stop")
    summary = client.get("/api/safety/metrics").json()["summary"]
    assert summary["unsafe_injected"] == 1
    assert summary["unsafe_prevented"] == 1
    assert summary["unsafe_missed"] == 0
    assert summary["violations_by_check"]["joint_limit"] >= 1


def test_unknown_fault_is_rejected(client):
    run_id = client.post("/api/runs", json={"source": "fake"}).json()["run_id"]
    assert client.post(f"/api/runs/{run_id}/faults", json={"fault": "teleport"}).status_code == 400
    client.post(f"/api/runs/{run_id}/stop")


def test_faults_injected_together_hit_the_same_chunk(client):
    run_id = client.post("/api/runs", json={"source": "fake"}).json()["run_id"]
    client.post(f"/api/runs/{run_id}/faults", json={"fault": "nan"})
    client.post(f"/api/runs/{run_id}/faults", json={"fault": "gripper"})
    wait_for(lambda: client.get("/api/safety/metrics").json()["summary"]["unsafe_injected"])
    client.post(f"/api/runs/{run_id}/stop")
    events = client.get(f"/api/sessions/{run_id}").json()["events"]
    faulted = [e["metadata"]["injected_faults"] for e in events if e["metadata"]]
    assert faulted == [["nan", "gripper"]]


def test_blocked_actions_halt_the_run_until_reset(client):
    from src.resources.run_service import get_manager

    get_manager().max_consecutive_blocks = 1
    run_id = client.post("/api/runs", json={"source": "fake"}).json()["run_id"]
    client.post(f"/api/runs/{run_id}/faults", json={"fault": "nan"})
    halted = wait_for(lambda: current(client)["state"] == "halted" and current(client))
    assert halted["consecutive_blocks"] == 1

    assert client.post(f"/api/runs/{run_id}/reset").json()["state"] == "running"
    assert client.post(f"/api/runs/{run_id}/reset").status_code == 409
    client.post(f"/api/runs/{run_id}/stop")


def test_paid_dream1_source_is_refused(client):
    response = client.post("/api/runs", json={"source": "dream1"})
    assert response.status_code == 403
    assert "Paid Dream-1 calls are disabled" in response.json()["detail"]
    assert current(client)["state"] == "idle"


class FakeSdkClient:
    """Stands in for dream.DreamClient in backend tests; never touches the network."""

    instances: list = []

    def __init__(self):
        self.policies, self.observations, self.calls = [], [], 0
        self.last_timing = {"total_ms": 300.0}
        FakeSdkClient.instances.append(self)

    def policy(self, config):
        self.policies.append(config)

    def set_observation(self, frames, observation, *, timestamp=None):
        self.observations.append((sorted(frames), observation["prompt"]))

    def get_action(self, *, commanded=None):
        self.calls += 1
        row = [0.0, 1.047, 1.047, 0.0, 0.0, 0.0, 1.0]
        return {"q_r_chunk": [list(row)] * 30, "q_l_chunk": [list(row)] * 30}

    def close(self):
        pass


@pytest.fixture()
def paid_enabled(monkeypatch, tmp_path):
    from dreamguard.sources import dream1
    from src.core_specs.configuration.config_loader import config_loader

    FakeSdkClient.instances = []
    monkeypatch.setattr(dream1, "CLIENT_FACTORY", FakeSdkClient)
    monkeypatch.setenv("DREAMGUARD_ALLOW_PAID", "1")
    monkeypatch.setitem(config_loader["dream"], "allow_paid_calls", True)
    monkeypatch.setitem(config_loader["dream"], "max_paid_calls_per_run", 2)
    monkeypatch.setitem(config_loader["dream"], "fixtures_dir", str(tmp_path / "fixtures"))
    return tmp_path / "fixtures"


def test_paid_calls_need_config_and_env(client, monkeypatch):
    from src.core_specs.configuration.config_loader import config_loader

    monkeypatch.setenv("DREAMGUARD_ALLOW_PAID", "1")
    assert client.post("/api/runs", json={"source": "dream1"}).status_code == 403
    monkeypatch.setenv("DREAMGUARD_ALLOW_PAID", "0")
    monkeypatch.setitem(config_loader["dream"], "allow_paid_calls", True)
    assert client.post("/api/runs", json={"source": "dream1"}).status_code == 403


def test_paid_run_needs_a_positive_budget(client, paid_enabled, monkeypatch):
    from src.core_specs.configuration.config_loader import config_loader

    monkeypatch.setitem(config_loader["dream"], "max_paid_calls_per_run", 0)
    response = client.post("/api/runs", json={"source": "dream1"})
    assert response.status_code == 403
    assert "max_paid_calls_per_run" in response.json()["detail"]
    assert FakeSdkClient.instances == []


def test_live_run_stops_at_the_paid_call_budget(client, paid_enabled):
    response = client.post("/api/runs", json={"source": "dream1", "prompt": "tidy up"})
    assert response.status_code == 201
    status = finish(client)
    assert status["state"] == "completed"
    assert status["paid_calls"] == 2
    assert status["chunks"] == 2

    [sdk] = FakeSdkClient.instances
    assert sdk.calls == 2
    assert sdk.policies[0]["_record"] is False
    assert sdk.observations[0] == (["video.overhead", "video.wrist_l", "video.wrist_r"], "tidy up")

    fixtures = list(paid_enabled.glob("*.jsonl"))
    assert len(fixtures) == 1
    assert len(fixtures[0].read_text(encoding="utf-8").splitlines()) == 2
    summary = client.get("/api/safety/metrics").json()["summary"]
    assert summary["sources"] == ["dream1"]
    assert summary["approved"] == 2


def test_replay_of_recorded_session(client):
    run_id = client.post("/api/runs", json={"source": "fake", "max_chunks": 3}).json()["run_id"]
    finish(client)
    response = client.post("/api/runs", json={"source": "replay", "replay_session_id": run_id})
    assert response.status_code == 201
    status = finish(client)
    assert status["source"] == "replay"
    assert status["chunks"] == 3
    assert client.get("/api/safety/metrics").json()["summary"]["approved"] == 3


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"source": "replay"}, 400),
        ({"source": "replay", "replay_session_id": "missing-session"}, 404),
        ({"source": "replay", "replay_session_id": "../escape"}, 400),
        ({"source": "teleport"}, 422),
        ({"source": "fake", "max_chunks": 0}, 422),
    ],
)
def test_invalid_run_requests(client, body, status):
    assert client.post("/api/runs", json=body).status_code == status


def test_actions_on_unknown_run_are_404(client):
    assert client.post("/api/runs/nope/stop").status_code == 404
    assert client.post("/api/runs/nope/faults", json={"fault": "nan"}).status_code == 404
