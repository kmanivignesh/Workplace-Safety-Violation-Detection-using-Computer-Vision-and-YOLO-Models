"""
Violation logger – writes to CSV and keeps a rolling in-memory log.
"""

import csv
import os
import threading
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "outputs", "violation_log.csv")
_HEADERS = ["timestamp", "violation_type", "persons", "helmet_viol", "vest_viol", "smoking", "snapshot"]

_lock   = threading.Lock()
_memory: list[dict] = []          # last 500 entries kept in RAM


def _ensure_file():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_HEADERS)
            writer.writeheader()


def log_event(stats: dict, snapshot_path: str = ""):
    """Append a detection event to the CSV log and memory."""
    _ensure_file()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "timestamp":    now,
        "violation_type": "|".join(stats.get("violations", [])) or "SAFE",
        "persons":      stats.get("total_persons", 0),
        "helmet_viol":  stats.get("helmet_violations", 0),
        "vest_viol":    stats.get("vest_violations", 0),
        "smoking":      stats.get("smoking", 0),
        "snapshot":     os.path.basename(snapshot_path),
    }
    with _lock:
        try:
            with open(LOG_PATH, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=_HEADERS)
                writer.writerow(row)
        except Exception:
            pass
        _memory.append(row)
        if len(_memory) > 500:
            _memory.pop(0)


def get_recent(n: int = 50) -> list[dict]:
    with _lock:
        return list(reversed(_memory[-n:]))


def get_log_path() -> str:
    return os.path.abspath(LOG_PATH)
