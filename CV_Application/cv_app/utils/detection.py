"""
Detection utility module for Worker Safety Monitoring System.
Handles PPE detection, smoking detection, and violation logic.
"""

import cv2
import numpy as np
from ultralytics import YOLO
import threading
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────
CONF_THRESHOLD = 0.25   # Keep at 0.25 - model detects at ~0.37; 0.4 misses it
IOU_THRESHOLD  = 0.15

# Colours (BGR)
COLORS = {
    "safe":    (0, 200, 80),
    "danger":  (0, 50,  255),
    "smoking": (0, 165, 255),
    "grey":    (180, 180, 180),
    "item":    (0, 220, 180),
}

# ─────────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────────
def compute_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0]); yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2]); yB = min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter == 0:
        return 0.0
    areaA = (boxA[2]-boxA[0]) * (boxA[3]-boxA[1])
    areaB = (boxB[2]-boxB[0]) * (boxB[3]-boxB[1])
    union = areaA + areaB - inter
    return inter / union if union > 0 else 0.0


def boxes_overlap(boxA, boxB):
    """Check if boxB (item) is associated with boxA (person)."""
    if compute_iou(boxA, boxB) >= IOU_THRESHOLD:
        return True
    # Centre-of-item-inside-person check (with 20% margin)
    cx = (boxB[0] + boxB[2]) / 2
    cy = (boxB[1] + boxB[3]) / 2
    w  = boxA[2] - boxA[0];  h = boxA[3] - boxA[1]
    return (boxA[0] - 0.2*w) <= cx <= (boxA[2] + 0.2*w) and \
           (boxA[1] - 0.2*h) <= cy <= (boxA[3] + 0.2*h)


# ─────────────────────────────────────────────────────────
# Model loader (singleton cache)
# ─────────────────────────────────────────────────────────
_model_cache = {}
_model_lock  = threading.Lock()


def load_model(model_path: str):
    with _model_lock:
        if model_path not in _model_cache:
            if not os.path.exists(model_path):
                logger.error(f"Model not found: {model_path}")
                return None
            try:
                _model_cache[model_path] = YOLO(model_path)
                logger.info(f"Loaded model: {model_path}")
            except Exception as e:
                logger.error(f"Failed to load {model_path}: {e}")
                return None
        return _model_cache[model_path]


# ─────────────────────────────────────────────────────────
# Core inference
# ─────────────────────────────────────────────────────────
def run_inference(model, frame):
    """Run YOLO on frame and return list of detection dicts."""
    detections = []
    try:
        results = model(frame, conf=CONF_THRESHOLD, verbose=False)
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cls_id = int(box.cls[0])
                conf   = float(box.conf[0])
                label  = r.names.get(cls_id, str(cls_id)).lower().strip()
                detections.append({"label": label, "conf": conf,
                                   "box": [x1, y1, x2, y2]})
    except Exception as e:
        logger.warning(f"Inference error: {e}")
    return detections


# ─────────────────────────────────────────────────────────
# PPE violation logic
# ─────────────────────────────────────────────────────────
def analyse_ppe(detections):
    persons = [d for d in detections if d["label"] == "person"]
    helmets = [d for d in detections if d["label"] == "helmet"]
    vests   = [d for d in detections if d["label"] in ("vest", "safety vest", "safety-vest")]

    results = []
    for p in persons:
        pb         = p["box"]
        has_helmet = any(boxes_overlap(pb, h["box"]) for h in helmets)
        has_vest   = any(boxes_overlap(pb, v["box"]) for v in vests)
        violations = []
        if not has_helmet:
            violations.append("NO HELMET")
        if not has_vest:
            violations.append("NO SAFETY VEST")
        results.append({
            "box": pb, "conf": p["conf"],
            "has_helmet": has_helmet, "has_vest": has_vest,
            "violations": violations,
        })
    return results


# ─────────────────────────────────────────────────────────
# Frame annotation (ASCII labels only - cv2 cannot render Unicode)
# ─────────────────────────────────────────────────────────
def _label(img, text, x, y, color, scale=0.52, thick=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    y = max(y, th + 4)
    # Dark background rectangle for readability
    cv2.rectangle(img, (x, y - th - 4), (x + tw + 6, y + 2), (10, 10, 15), -1)
    cv2.putText(img, text, (x + 3, y), font, scale, color, thick, cv2.LINE_AA)
    return th + 6


def draw_detections(frame, ppe_analysis, raw_ppe_dets, smoking_dets):
    out = frame.copy()
    H, W = out.shape[:2]

    stats = {
        "total_persons":     len(ppe_analysis),
        "helmet_violations": 0,
        "vest_violations":   0,
        "smoking":           len(smoking_dets),
        "violations":        [],
    }

    # ── Person boxes ──────────────────────────────────────
    for p in ppe_analysis:
        x1, y1, x2, y2 = [max(0, c) for c in p["box"]]
        x2 = min(x2, W-1); y2 = min(y2, H-1)
        violations = p["violations"]
        color = COLORS["danger"] if violations else COLORS["safe"]

        # Draw person bounding box
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

        # Corner accent marks
        corner_len = 12
        cv2.line(out, (x1, y1), (x1+corner_len, y1), color, 3)
        cv2.line(out, (x1, y1), (x1, y1+corner_len), color, 3)
        cv2.line(out, (x2, y1), (x2-corner_len, y1), color, 3)
        cv2.line(out, (x2, y1), (x2, y1+corner_len), color, 3)
        cv2.line(out, (x1, y2), (x1+corner_len, y2), color, 3)
        cv2.line(out, (x1, y2), (x1, y2-corner_len), color, 3)
        cv2.line(out, (x2, y2), (x2-corner_len, y2), color, 3)
        cv2.line(out, (x2, y2), (x2, y2-corner_len), color, 3)

        # Labels above box (ASCII only for cv2 compat)
        lines = [f"PERSON {p['conf']:.0%}"]
        lines += ["[OK] Helmet" if p["has_helmet"] else "[NO HELMET]"]
        lines += ["[OK] Vest"   if p["has_vest"]   else "[NO VEST]"]

        y_off = max(y1 - 4, 14)
        for text in lines:
            col = (COLORS["safe"]   if text.startswith("[OK]") else
                   COLORS["danger"] if text.startswith("[NO]") else color)
            used = _label(out, text, x1, y_off, col)
            y_off -= used

        if "NO HELMET" in violations:
            stats["helmet_violations"] += 1
            if "NO HELMET" not in stats["violations"]:
                stats["violations"].append("NO HELMET")
        if "NO SAFETY VEST" in violations:
            stats["vest_violations"] += 1
            if "NO SAFETY VEST" not in stats["violations"]:
                stats["violations"].append("NO SAFETY VEST")

    # ── Helmet / Vest item boxes ───────────────────────────
    for d in raw_ppe_dets:
        if d["label"] == "helmet":
            x1, y1, x2, y2 = d["box"]
            cv2.rectangle(out, (x1, y1), (x2, y2), COLORS["item"], 1)
            _label(out, f"Helmet {d['conf']:.0%}", x1, max(y1-2, 14),
                   COLORS["item"], 0.44)
        elif d["label"] in ("vest", "safety vest", "safety-vest"):
            x1, y1, x2, y2 = d["box"]
            cv2.rectangle(out, (x1, y1), (x2, y2), COLORS["item"], 1)
            _label(out, f"Vest {d['conf']:.0%}", x1, max(y1-2, 14),
                   COLORS["item"], 0.44)

    # ── Smoking boxes ──────────────────────────────────────
    for d in smoking_dets:
        x1, y1, x2, y2 = d["box"]
        cv2.rectangle(out, (x1, y1), (x2, y2), COLORS["smoking"], 2)
        _label(out, f"SMOKING {d['conf']:.0%}", x1, max(y1-2, 14),
               COLORS["smoking"], 0.55, 2)

    if smoking_dets and "SMOKING DETECTED" not in stats["violations"]:
        stats["violations"].append("SMOKING DETECTED")

    # ── Timestamp watermark ────────────────────────────────
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    cv2.putText(out, ts, (10, H-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLORS["grey"], 1, cv2.LINE_AA)

    return out, stats


# ─────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────
def process_frame(frame, ppe_model, smoking_model):
    """Run both models in parallel (each on its own frame copy)."""
    ppe_holder = [None]
    smk_holder = [None]

    def _ppe():
        ppe_holder[0] = run_inference(ppe_model, frame.copy())

    def _smk():
        smk_holder[0] = run_inference(smoking_model, frame.copy())

    t1 = threading.Thread(target=_ppe, daemon=True)
    t2 = threading.Thread(target=_smk, daemon=True)
    t1.start(); t2.start()
    t1.join();  t2.join()

    raw_ppe      = ppe_holder[0] or []
    smoking_dets = [d for d in (smk_holder[0] or [])
                    if "smok" in d["label"] or "cigarette" in d["label"]]

    ppe_analysis    = analyse_ppe(raw_ppe)
    annotated, stats = draw_detections(frame, ppe_analysis, raw_ppe, smoking_dets)
    return annotated, stats
