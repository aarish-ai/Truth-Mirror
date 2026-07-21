"""Per-request pipeline status tracking."""

import threading
import time

_status_lock = threading.Lock()
_statuses: dict[str, dict] = {}

# Auto-expire stale entries after 10 minutes (in seconds)
_EXPIRY_SECONDS = 600


def set_stage(stage_name: str, request_id: str = "__global__") -> None:
    """
    Update the pipeline stage for a specific request.
    Falls back to a global key if no request_id is provided (backward compat).
    """
    with _status_lock:
        _statuses[request_id] = {
            "stage": stage_name,
            "updated_at": time.time(),
        }


def get_status(request_id: str = "__global__") -> dict:
    """
    Retrieve the pipeline stage for a specific request.
    Returns {"stage": "idle"} if the request_id is unknown.
    """
    with _status_lock:
        entry = _statuses.get(request_id)
        if entry:
            return {"stage": entry["stage"]}
        return {"stage": "idle"}


def clear_status(request_id: str) -> None:
    """Remove a request's status entry after completion."""
    with _status_lock:
        _statuses.pop(request_id, None)


def cleanup_stale() -> int:
    """Remove entries older than _EXPIRY_SECONDS. Returns count removed."""
    now = time.time()
    removed = 0
    with _status_lock:
        stale_keys = [
            k for k, v in _statuses.items()
            if now - v["updated_at"] > _EXPIRY_SECONDS
        ]
        for k in stale_keys:
            del _statuses[k]
            removed += 1
    return removed
