import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

class RunTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.claim: str = ""
        self.start_time: float = 0.0
        self.events: List[Dict[str, Any]] = []

    def reset(self, claim: str):
        with self._lock:
            self.claim = claim
            self.start_time = time.time()
            self.events = []

    def record(self, stage: str, model: str, provider: str, status: str, key_index: Optional[int] = None):
        with self._lock:
            self.events.append({
                "stage": stage,
                "model": model,
                "provider": provider,
                "status": status,
                "key_index": key_index
            })

    def get_stage_summary(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.events)

    def elapsed_seconds(self) -> float:
        if self.start_time == 0.0:
            return 0.0
        return time.time() - self.start_time

class TrackerRegistry:
    """Thread-safe registry of per-request RunTracker instances.
    
    Falls back to a default tracker for backward compatibility
    when no request_id context is set.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._trackers: Dict[str, RunTracker] = {}
        self._default = RunTracker()
        # Thread-local storage for current request context
        self._local = threading.local()
    
    def get_or_create(self, request_id: str) -> RunTracker:
        """Get or create a tracker for a specific request_id."""
        with self._lock:
            if request_id not in self._trackers:
                self._trackers[request_id] = RunTracker()
            return self._trackers[request_id]
    
    def set_current(self, request_id: str) -> None:
        """Set the current request context for this thread."""
        self._local.request_id = request_id
    
    def clear_current(self) -> None:
        """Clear the current request context for this thread."""
        self._local.request_id = None
    
    def remove(self, request_id: str) -> None:
        """Remove a tracker after the request is done."""
        with self._lock:
            self._trackers.pop(request_id, None)
    
    # ── Proxy methods for backward compatibility ──
    # These delegate to the current thread's tracker or the default.
    
    def _current(self) -> RunTracker:
        request_id = getattr(self._local, 'request_id', None)
        if request_id:
            return self.get_or_create(request_id)
        return self._default
    
    def reset(self, claim: str):
        self._current().reset(claim)
    
    def record(self, stage: str, model: str, provider: str, status: str, key_index: Optional[int] = None):
        self._current().record(stage, model, provider, status, key_index)
    
    def get_stage_summary(self) -> List[Dict[str, Any]]:
        return self._current().get_stage_summary()
    
    def elapsed_seconds(self) -> float:
        return self._current().elapsed_seconds()


# Module-level singleton — backward compatible, but now dispatches per-request
tracker = TrackerRegistry()
