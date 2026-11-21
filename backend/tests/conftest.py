import socket
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.core_specs.configuration.config_loader import config_loader  # noqa: E402

from src.utils.limiter import limiter  # noqa: E402

# Tests run the simulation as fast as possible, never allow paid calls, and poll endpoints
# far more often than the per-minute rate limits allow.
config_loader["simulation"]["realtime"] = False
config_loader["dream"]["allow_paid_calls"] = False
limiter.enabled = False


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """Backend tests must never reach Dream Labs (or anything else off this machine)."""
    original = socket.socket.connect

    def guarded(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError(f"Test attempted an external network connection to {address}")
        return original(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture()
def sessions_dir(tmp_path, monkeypatch):
    from src.resources import session_service

    directory = tmp_path / "sessions"
    monkeypatch.setattr(session_service, "SESSIONS_DIR", directory)
    return directory


@pytest.fixture()
def client(sessions_dir):
    from main import app

    with TestClient(app) as test_client:
        yield test_client


def wait_for(predicate, timeout=20.0, interval=0.05):
    """Poll until ``predicate()`` returns a truthy value; fail on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError("Timed out waiting for condition")
