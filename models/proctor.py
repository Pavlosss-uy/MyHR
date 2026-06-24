"""Proctoring — OpenCV-only integrity analysis for interview video frames.

Detects the cheating signals the product needs, with NO TensorFlow dependency
(TensorFlow has no wheel for Python 3.14, so DeepFace cannot run here):

  - out-of-frame   : no face visible
  - multiple people : more than one face in frame
  - looking-away    : head turned / tilted away (e.g. glancing down at a phone)

Detection backend
-----------------
Primary: **YuNet** (cv2.FaceDetectorYN) — a tiny ONNX face detector that also
returns 5 facial landmarks (both eyes, nose, mouth corners). From the landmarks we
estimate head YAW (left/right turn) and vertical foreshortening (up/down tilt), so
looking down at a phone is caught even when the head stays roughly centered.

Fallback: Haar cascade (bounding box only) if the YuNet model file is missing —
in that mode looking-away degrades to a horizontal-offset proxy.

Honesty note: this is HEAD-POSE estimation, not certified eye-gaze. A candidate who
moves only their eyes (head perfectly still) cannot be detected without iris
tracking (MediaPipe), which has no Python 3.14 wheel.

Runs synchronously; callers must wrap in `asyncio.to_thread` so the FastAPI event
loop is never blocked. A lock serializes access to the shared detector.
"""

import os
import time
import threading

import cv2
import numpy as np

# --- tuning ---
_YUNET_PATH = os.path.join(os.path.dirname(__file__), "weights", "face_detection_yunet_2023mar.onnx")
# Calibrated against a real 640×480 webcam (straight-ahead noise tops out at
# yaw≈0.21 / vspan≈1.28; genuine look-aways start at yaw≈0.25 / vspan≈1.31).
# Per-frame sensitivity is fine because the per-ANSWER aggregate requires the
# behaviour to persist across ≥30% of frames before it counts as suspicious.
_SCORE_THRESHOLD = 0.70          # YuNet face-confidence floor (rejects false positives)
_YAW_THRESHOLD = 0.25            # |nose offset from eye-midline| / inter-ocular  → turned L/R
_VSPAN_MIN = 0.75               # vertical eye→mouth span / inter-ocular below this → looking down
_VSPAN_MAX = 1.45               # above this → head turned/tilted (perspective inflates span)
_GAZE_OFFSET_THRESHOLD = 0.35    # Haar fallback: horizontal face-center offset

_lock = threading.Lock()
_yunet = None
_yunet_failed = False
_haar = None


def _get_yunet():
    global _yunet, _yunet_failed
    if _yunet is None and not _yunet_failed:
        if not os.path.exists(_YUNET_PATH):
            _yunet_failed = True
            return None
        try:
            _yunet = cv2.FaceDetectorYN.create(_YUNET_PATH, "", (320, 320), _SCORE_THRESHOLD)
        except Exception:
            _yunet_failed = True
            _yunet = None
    return _yunet


def _get_haar():
    global _haar
    if _haar is None:
        _haar = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _haar


def _empty_result(ts: float) -> dict:
    return {
        "face_count": 0,
        "face_present": False,
        "multiple_faces": False,
        "looking_away": False,
        "timestamp": ts,
    }


def warmup() -> None:
    """Load the detector once at startup so the first frame is fast."""
    try:
        if _get_yunet() is not None:
            print("[OK]   Proctor ready (YuNet landmark detector).")
        else:
            _get_haar()
            print("[WARN] YuNet model missing — proctor using Haar fallback (no tilt detection).")
    except Exception as e:
        print(f"[WARN] Proctor warmup skipped ({e}).")


def _head_pose_from_landmarks(face_row):
    """Estimate head pose from YuNet's 5 landmarks.

    Returns (looking_away: bool, yaw: float, vspan: float) — yaw/vspan exposed for
    calibration (so thresholds can be tuned against a real webcam).
    """
    re = np.array([face_row[4], face_row[5]])    # right eye
    le = np.array([face_row[6], face_row[7]])    # left eye
    nose = np.array([face_row[8], face_row[9]])  # nose tip
    rm = np.array([face_row[10], face_row[11]])  # right mouth corner
    lm = np.array([face_row[12], face_row[13]])  # left mouth corner

    eye_mid = (re + le) / 2.0
    mouth_mid = (rm + lm) / 2.0
    inter_ocular = float(np.linalg.norm(re - le))
    if inter_ocular < 1e-3:
        return False, 0.0, 0.0

    # Yaw: how far the nose sits from the midline between the eyes (left/right turn).
    yaw = abs(float(nose[0] - eye_mid[0])) / inter_ocular
    # Vertical foreshortening: eye→mouth span shrinks looking down, grows looking up.
    vspan = abs(float(mouth_mid[1] - eye_mid[1])) / inter_ocular

    looking_away = bool(yaw > _YAW_THRESHOLD or vspan < _VSPAN_MIN or vspan > _VSPAN_MAX)
    return looking_away, round(yaw, 3), round(vspan, 3)


def _analyze_yunet(img_bgr, ts: float):
    detector = _get_yunet()
    if detector is None:
        return None  # signal caller to use Haar fallback

    img_h, img_w = img_bgr.shape[:2]
    with _lock:
        detector.setInputSize((img_w, img_h))
        _, faces = detector.detect(img_bgr)

    if faces is None or len(faces) == 0:
        return _empty_result(ts)

    face_count = len(faces)
    # Primary = highest-confidence face (last column is the score).
    primary = max(faces, key=lambda f: float(f[14]))
    looking_away, yaw, vspan = _head_pose_from_landmarks(primary)

    return {
        "face_count": int(face_count),
        "face_present": True,
        "multiple_faces": bool(face_count > 1),
        "looking_away": looking_away,
        "yaw": yaw,        # diagnostic (for threshold calibration)
        "vspan": vspan,    # diagnostic (for threshold calibration)
        "timestamp": float(ts),
    }


def _analyze_haar(img_bgr, ts: float):
    img_h, img_w = img_bgr.shape[:2]
    gray = cv2.equalizeHist(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY))
    cascade = _get_haar()
    with _lock:
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=6, minSize=(80, 80),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
    face_count = len(faces) if faces is not None and len(faces) > 0 else 0
    if face_count == 0:
        return _empty_result(ts)

    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))
    offset = abs((int(x) + int(w) / 2.0) - img_w / 2.0) / max(img_w, 1)
    return {
        "face_count": int(face_count),
        "face_present": True,
        "multiple_faces": bool(face_count > 1),
        "looking_away": bool(offset > _GAZE_OFFSET_THRESHOLD),
        "timestamp": float(ts),
    }


def analyze(img_bgr) -> dict:
    """Analyze one BGR frame (OpenCV ndarray) for proctoring signals."""
    ts = time.time()
    if img_bgr is None:
        return _empty_result(ts)
    try:
        result = _analyze_yunet(img_bgr, ts)
        if result is None:
            result = _analyze_haar(img_bgr, ts)
        return result
    except Exception as e:
        res = _empty_result(ts)
        res["error"] = str(e)
        return res


def aggregate(frames: list) -> dict:
    """Roll up per-frame results for one answer into an integrity summary."""
    if not frames:
        return {
            "face_absent_pct": 0.0,
            "looking_away_pct": 0.0,
            "multiple_faces_detected": False,
            "frames_analyzed": 0,
            "suspicious": False,
        }

    total = len(frames)
    present = [f for f in frames if f.get("face_present", False)]
    face_absent_pct = round((total - len(present)) / total, 3)
    looking_away_pct = round(
        sum(1 for f in present if f.get("looking_away", False)) / total, 3
    )
    multiple_faces = any(f.get("multiple_faces", False) for f in frames)
    suspicious = bool(
        multiple_faces or face_absent_pct > 0.20 or looking_away_pct > 0.30
    )

    return {
        "face_absent_pct": face_absent_pct,
        "looking_away_pct": looking_away_pct,
        "multiple_faces_detected": multiple_faces,
        "frames_analyzed": total,
        "suspicious": suspicious,
    }
