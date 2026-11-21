from collections.abc import Mapping, Sequence
from typing import Any

from .guard import SafetyGuard


def guarded_get_action(
    client: Any,
    guard: SafetyGuard,
    *,
    current_joints: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    """Get one Dream-1 action chunk and fail closed unless DreamGuard approves it."""
    action = client.get_action()
    return guard.approve(action, current_joints=current_joints)
