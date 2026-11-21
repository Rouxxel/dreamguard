import pytest
from starlette.websockets import WebSocketDisconnect


def test_events_socket_sends_status_then_events(client):
    with client.websocket_connect("/ws/events") as socket:
        first = socket.receive_json()
        assert first["type"] == "run"
        assert first["run"]["state"] == "idle"

        client.post("/api/runs", json={"source": "fake", "max_chunks": 2})
        messages = []
        while sum(m["type"] == "event" for m in messages) < 2:
            messages.append(socket.receive_json())
        events = [m["event"] for m in messages if m["type"] == "event"]
        assert [e["sequence"] for e in events] == [1, 2]
        assert events[0]["report"]["decision"] == "APPROVE"
        assert any(m["type"] == "run" and m["run"]["state"] == "running" for m in messages)


def test_events_socket_rejects_foreign_origins(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/ws/events", headers={"origin": "http://untrusted.invalid"}
        ) as socket:
            socket.receive_json()
    assert exc.value.code == 1008


def test_events_socket_accepts_dashboard_origin(client):
    with client.websocket_connect(
        "/ws/events", headers={"origin": "http://localhost:5173"}
    ) as socket:
        assert socket.receive_json()["type"] == "run"


def test_camera_stream_returns_mjpeg_frames(client):
    health = client.get("/").json()
    if health["camera"] != "available":
        pytest.skip("No OpenGL rendering backend available")
    response = client.get("/api/stream/camera/overhead", params={"max_frames": 2})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert response.content.count(b"Content-Type: image/jpeg") == 2
    assert b"\xff\xd8" in response.content  # JPEG start-of-image marker


def test_unknown_camera_is_404(client):
    assert client.get("/api/stream/camera/basement").status_code == 404
