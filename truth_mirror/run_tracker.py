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

# Module-level singleton
tracker = RunTracker()
