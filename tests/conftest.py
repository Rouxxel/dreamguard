import socket

import pytest

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """Tests must never reach Dream Labs (or anything else off this machine)."""
    original = socket.socket.connect

    def guarded(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOCAL_HOSTS:
            raise AssertionError(f"Test attempted an external network connection to {address}")
        return original(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded)
