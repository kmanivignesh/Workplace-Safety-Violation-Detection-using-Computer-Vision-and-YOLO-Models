"""
app.py - Flask backend for Worker Safety Monitoring System.

Routes
------
GET  /                       -> Dashboard (index.html)
GET  /video_feed             -> MJPEG webcam stream
POST /start_camera           -> Activate webcam
POST /stop_camera            -> Deactivate webcam
POST /upload_image           -> Process a static image
POST /upload_video           -> Process & save a video
GET  /download/<filename>    -> Serve processed file
GET  /api/stats              -> Latest frame stats (JSON)
GET  /api/log                -> Recent violation log (JSON)
GET  /download_report        -> Download violation CSV
POST /toggle_voice           -> Enable/disable voice alerts
GET  /api/status             -> Server status (JSON)
GET  /video_status/<job_id>  -> Video processing status
"""

import os
import time
import threading
import logging
import base64
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from flask import (Flask, Response, jsonify, render_template,
                   request, send_file, send_from_directory, abort)
from werkzeug.utils import secure_filename

from utils.detection   import load_model, process_frame
from utils.voice_alert import get_alert_engine
from utils.logger      import log_event, get_recent, get_log_path

# ─────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Flask app
# ─────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.update(
    SECRET_KEY         = os.urandom(24),
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024,   # 500 MB
    UPLOAD_FOLDER      = os.path.join("static", "uploads"),
    OUTPUT_FOLDER      = os.path.join("static", "outputs"),
    SNAPSHOT_FOLDER    = os.path.join("static", "outputs", "snapshots"),
    MODEL_PPE          = os.path.join("models", "ppe.pt"),
    MODEL_SMOKING      = os.path.join("models", "smoking.pt"),
    ALLOWED_IMAGE_EXT  = {"png", "jpg", "jpeg", "bmp", "webp"},
    ALLOWED_VIDEO_EXT  = {"mp4", "avi", "mov", "mkv", "webm"},
)

# Ensure directories exist
for folder in [app.config["UPLOAD_FOLDER"],
               app.config["OUTPUT_FOLDER"],
               app.config["SNAPSHOT_FOLDER"]]:
    os.makedirs(folder, exist_ok=True)

# ─────────────────────────────────────────────────────────
# Load models (lazy - if files are missing, warn gracefully)
# ─────────────────────────────────────────────────────────
ppe_model     = None
smoking_model = None


def _load_models():
    global ppe_model, smoking_model
    ppe_model     = load_model(app.config["MODEL_PPE"])
    smoking_model = load_model(app.config["MODEL_SMOKING"])
    if ppe_model:
        logger.info("PPE model ready.")
    else:
        logger.warning("PPE model not found - detection will be skipped.")
    if smoking_model:
        logger.info("Smoking model ready.")
    else:
        logger.warning("Smoking model not found - detection will be skipped.")


threading.Thread(target=_load_models, daemon=True).start()

# ─────────────────────────────────────────────────────────
# Webcam state
# ─────────────────────────────────────────────────────────
_cam_lock   = threading.Lock()
_cap        = None          # cv2.VideoCapture
_cam_active = False

_latest_stats = {
    "total_persons":     0,
    "helmet_violations": 0,
    "vest_violations":   0,
    "smoking":           0,
    "violations":        [],
    "fps":               0.0,
    "timestamp":         "",
    "status":            "IDLE",
}
_stats_lock = threading.Lock()

_frame_count             = 0
_fps_time                = time.time()
_last_violation_snapshot = 0   # throttle snapshots

SNAPSHOT_INTERVAL = 10   # seconds between auto-snapshots on violation

# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────
def _allowed_file(filename: str, kind: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if kind == "image":
        return ext in app.config["ALLOWED_IMAGE_EXT"]
    return ext in app.config["ALLOWED_VIDEO_EXT"]


def _status_from_stats(stats: dict) -> str:
    if stats["smoking"] > 0:
        return "DANGER"
    if stats["helmet_violations"] > 0 or stats["vest_violations"] > 0:
        return "WARNING"
    if stats["total_persons"] > 0:
        return "SAFE"
    return "IDLE"


def _run_both_models(frame: np.ndarray):
    """Run both models (or just one if the other is missing)."""
    if ppe_model and smoking_model:
        return process_frame(frame, ppe_model, smoking_model)
    if ppe_model:
        return process_frame(frame, ppe_model, ppe_model)
    if smoking_model:
        return process_frame(frame, smoking_model, smoking_model)
    return frame.copy(), {"total_persons":0,"helmet_violations":0,
                          "vest_violations":0,"smoking":0,"violations":[]}


def _maybe_save_snapshot(frame: np.ndarray, stats: dict):
    """Save a snapshot when violations are detected (throttled)."""
    global _last_violation_snapshot
    if not stats.get("violations"):
        return ""
    now = time.time()
    if now - _last_violation_snapshot < SNAPSHOT_INTERVAL:
        return ""
    _last_violation_snapshot = now
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"violation_{ts}.jpg"
    path = os.path.join(app.config["SNAPSHOT_FOLDER"], name)
    cv2.imwrite(path, frame)
    return path


# ─────────────────────────────────────────────────────────
# MJPEG generator
# ─────────────────────────────────────────────────────────
def _gen_frames():
    global _frame_count, _fps_time, _cap, _cam_active

    voice = get_alert_engine()

    while True:
        with _cam_lock:
            active = _cam_active
            cap    = _cap

        if not active or cap is None:
            # Stream a "camera off" placeholder frame
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Camera Off", (220, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (80, 80, 100), 2)
            _, buf = cv2.imencode(".jpg", placeholder)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                   + buf.tobytes() + b"\r\n")
            time.sleep(0.1)
            continue

        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        annotated, stats = _run_both_models(frame)

        # FPS calculation
        _frame_count += 1
        elapsed = time.time() - _fps_time
        if elapsed >= 1.0:
            fps = _frame_count / elapsed
            _frame_count = 0
            _fps_time    = time.time()
        else:
            fps = _frame_count / elapsed if elapsed > 0 else 0

        # Overlay FPS on frame
        cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2)

        status = _status_from_stats(stats)
        stats["fps"]       = round(fps, 1)
        stats["timestamp"] = datetime.now().strftime("%H:%M:%S")
        stats["status"]    = status

        with _stats_lock:
            _latest_stats.update(stats)

        # Voice alerts
        voice.trigger_violations(stats["violations"])

        # Auto-snapshot on violation
        snap = _maybe_save_snapshot(annotated, stats)
        if snap:
            log_event(stats, snap)

        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 82])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
               + buf.tobytes() + b"\r\n")


# ─────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    ppe_ok     = os.path.exists(app.config["MODEL_PPE"])
    smoking_ok = os.path.exists(app.config["MODEL_SMOKING"])
    return render_template("index.html",
                           ppe_model_ok=ppe_ok,
                           smoking_model_ok=smoking_ok)


@app.route("/video_feed")
def video_feed():
    return Response(_gen_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/start_camera", methods=["POST"])
def start_camera():
    global _cap, _cam_active
    with _cam_lock:
        if _cam_active:
            return jsonify({"ok": True, "message": "Already running"})
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)
            cap.set(cv2.CAP_PROP_FPS,           30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE,     1)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return jsonify({"ok": False, "message": "Cannot open camera"}), 500
            _cap        = cap
            _cam_active = True
            logger.info("Camera started.")
            return jsonify({"ok": True, "message": "Camera started"})
        except Exception as e:
            return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/stop_camera", methods=["POST"])
def stop_camera():
    global _cap, _cam_active
    with _cam_lock:
        _cam_active = False
        if _cap:
            _cap.release()
            _cap = None
    with _stats_lock:
        _latest_stats.update({
            "total_persons":0,"helmet_violations":0,
            "vest_violations":0,"smoking":0,"violations":[],
            "fps":0.0,"timestamp":"","status":"IDLE"
        })
    logger.info("Camera stopped.")
    return jsonify({"ok": True, "message": "Camera stopped"})


@app.route("/api/stats")
def api_stats():
    with _stats_lock:
        return jsonify(dict(_latest_stats))


@app.route("/api/log")
def api_log():
    return jsonify(get_recent(50))


@app.route("/api/status")
def api_status():
    return jsonify({
        "ppe_model":     ppe_model is not None,
        "smoking_model": smoking_model is not None,
        "camera_active": _cam_active,
        "voice_enabled": get_alert_engine().is_enabled,
    })


@app.route("/toggle_voice", methods=["POST"])
def toggle_voice():
    eng = get_alert_engine()
    eng.set_enabled(not eng.is_enabled)
    return jsonify({"ok": True, "voice_enabled": eng.is_enabled})


# ── Image upload ───────────────────────────────────────────
@app.route("/upload_image", methods=["POST"])
def upload_image():
    if "image" not in request.files:
        return jsonify({"ok": False, "message": "No file uploaded"}), 400
    file = request.files["image"]
    if not file.filename or not _allowed_file(file.filename, "image"):
        return jsonify({"ok": False, "message": "Invalid file type"}), 400

    fname   = secure_filename(file.filename)
    in_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
    file.save(in_path)

    frame = cv2.imread(in_path)
    if frame is None:
        return jsonify({"ok": False, "message": "Cannot read image"}), 422

    annotated, stats = _run_both_models(frame)
    stats["status"]  = _status_from_stats(stats)

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"processed_{ts}_{fname}"
    out_path = os.path.join(app.config["OUTPUT_FOLDER"], out_name)
    cv2.imwrite(out_path, annotated)

    log_event(stats, out_path)

    # Encode annotated image to base64 for inline preview
    _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])
    b64    = base64.b64encode(buf).decode()

    return jsonify({
        "ok":          True,
        "image_b64":   b64,
        "output_file": out_name,
        "stats":       stats,
    })


# ── Video upload ───────────────────────────────────────────
_video_progress: dict = {}


@app.route("/upload_video", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return jsonify({"ok": False, "message": "No file uploaded"}), 400
    file = request.files["video"]
    if not file.filename or not _allowed_file(file.filename, "video"):
        return jsonify({"ok": False, "message": "Invalid file type"}), 400

    fname   = secure_filename(file.filename)
    in_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
    file.save(in_path)

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"processed_{ts}_{fname}"
    out_path = os.path.join(app.config["OUTPUT_FOLDER"], out_name)

    def _process_video():
        cap = cv2.VideoCapture(in_path)
        if not cap.isOpened():
            _video_progress[out_name] = "error"
            return
        fps    = cap.get(cv2.CAP_PROP_FPS) or 25
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

        cumulative = {"total_persons":0,"helmet_violations":0,
                      "vest_violations":0,"smoking":0,"violations":[]}
        frame_idx  = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            annotated, stats = _run_both_models(frame)
            cv2.putText(annotated, f"Frame: {frame_idx}/{total}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 2)
            writer.write(annotated)

            cumulative["total_persons"]    += stats["total_persons"]
            cumulative["helmet_violations"] += stats["helmet_violations"]
            cumulative["vest_violations"]   += stats["vest_violations"]
            cumulative["smoking"]           += stats["smoking"]
            for v in stats["violations"]:
                if v not in cumulative["violations"]:
                    cumulative["violations"].append(v)

            frame_idx += 1
            _video_progress[out_name] = f"{frame_idx}/{total}"

        cap.release()
        writer.release()
        log_event(cumulative, out_path)
        _video_progress[out_name] = "done"

    _video_progress[out_name] = "processing"
    threading.Thread(target=_process_video, daemon=True).start()

    return jsonify({
        "ok":      True,
        "job_id":  out_name,
        "message": "Video processing started",
    })


@app.route("/video_status/<job_id>")
def video_status(job_id):
    status = _video_progress.get(job_id, "unknown")
    return jsonify({"job_id": job_id, "status": status})


# ── Downloads ──────────────────────────────────────────────
@app.route("/download/<filename>")
def download_file(filename):
    safe = secure_filename(filename)
    path = os.path.join(app.config["OUTPUT_FOLDER"], safe)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)


@app.route("/download_report")
def download_report():
    p = get_log_path()
    if not os.path.exists(p):
        return jsonify({"ok": False, "message": "No log yet"}), 404
    return send_file(p, as_attachment=True, download_name="violation_report.csv")


# ── Static assets quick-serve ──────────────────────────────
@app.route("/static/outputs/<path:filename>")
def serve_output(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename)


# ── Snapshot listing ───────────────────────────────────────
@app.route("/api/snapshots")
def api_snapshots():
    """Return list of recent snapshot filenames."""
    snap_dir = app.config["SNAPSHOT_FOLDER"]
    try:
        files = sorted(
            [f for f in os.listdir(snap_dir) if f.endswith(".jpg")],
            reverse=True
        )[:12]
        return jsonify({"snapshots": files})
    except Exception:
        return jsonify({"snapshots": []})


# ─────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
