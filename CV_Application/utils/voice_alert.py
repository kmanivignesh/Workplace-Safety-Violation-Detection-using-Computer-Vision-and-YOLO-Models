"""
Voice Alert System.
- Continuous: repeats every REPEAT_INTERVAL seconds while violation is active.
- Stops automatically when violation is resolved.
- Uses subprocess per TTS call to avoid Windows COM threading issues.
"""

import subprocess
import sys
import threading
import time
import logging

logger = logging.getLogger(__name__)

REPEAT_INTERVAL = 4   # seconds between repeats of the same alert

MESSAGES = {
    "NO HELMET":        "Please wear a helmet",
    "NO SAFETY VEST":   "Please wear a safety vest",
    "SMOKING DETECTED": "Smoking detected. Smoking is prohibited",
}

ALERT_ORDER = ["NO HELMET", "NO SAFETY VEST", "SMOKING DETECTED"]


def _speak(text: str):
    """Spawn a fresh Python process to speak text. Blocks until done."""
    try:
        script = (
            "import pyttsx3; "
            "e = pyttsx3.init(); "
            "e.setProperty('rate', 150); "
            "e.setProperty('volume', 1.0); "
            f"e.say('{text}'); "
            "e.runAndWait()"
        )
        subprocess.run(
            [sys.executable, "-c", script],
            timeout=20,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.warning(f"TTS failed: {exc}")


class VoiceAlertEngine:
    def __init__(self):
        self._lock    = threading.Lock()
        self._active: set = set()   # currently active violations
        self._enabled = True
        self._thread  = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        logger.info("VoiceAlertEngine started.")

    def _worker(self):
        last_spoken: dict = {}

        while True:
            with self._lock:
                active  = set(self._active)
                enabled = self._enabled

            now = time.time()

            if enabled and active:
                for key in ALERT_ORDER:
                    if key not in active:
                        continue
                    if now - last_spoken.get(key, 0) >= REPEAT_INTERVAL:
                        last_spoken[key] = time.time()
                        logger.info(f"[VOICE] {key}")
                        _speak(MESSAGES[key])          # blocks ~2-3 s
                        # Re-check active after speaking
                        with self._lock:
                            active = set(self._active)

            # Clear cooldowns for resolved violations
            for key in list(last_spoken):
                if key not in active:
                    del last_spoken[key]

            time.sleep(0.2)

    # ── Public API ────────────────────────────────────────
    def trigger_violations(self, violations: list):
        """Called every frame with the current list of violations."""
        with self._lock:
            self._active = {v for v in violations if v in MESSAGES}

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if not enabled:
            with self._lock:
                self._active.clear()

    @property
    def is_enabled(self) -> bool:
        return self._enabled


# ── Singleton ─────────────────────────────────────────────
_alert_engine = None
_engine_lock  = threading.Lock()


def get_alert_engine() -> VoiceAlertEngine:
    global _alert_engine
    with _engine_lock:
        if _alert_engine is None:
            _alert_engine = VoiceAlertEngine()
    return _alert_engine
