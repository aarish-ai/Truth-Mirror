import threading

_status_lock = threading.Lock()
_status = {
    "stage": "idle"
}

def set_stage(stage_name: str):
    """
    Update the global pipeline stage.
    Used by the frontend to display progress.
    """
    with _status_lock:
        _status["stage"] = stage_name

def get_status() -> dict:
    """
    Retrieve the current pipeline stage.
    """
    with _status_lock:
        return _status.copy()
