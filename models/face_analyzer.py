import time
import cv2
import numpy as np
from collections import Counter
from typing import Optional


_face_cascade = None


def _get_cascade():
    global _face_cascade
    if _face_cascade is None:
        xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(xml)
    return _face_cascade


def _decode_image(image_bytes: bytes) -> Optional[np.ndarray]:
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def analyze_frame(image_bytes: bytes) -> dict:
    """
    Analyze a single JPEG frame for face presence and gaze direction.

    Uses OpenCV Haar cascade — no TensorFlow required, works on Python 3.14.
    Emotion detection is skipped (audio emotion from wav2vec2 covers this).

    Returns:
      dominant_emotion : always "unknown" (use audio emotion instead)
      emotion_scores   : {}
      face_count       : int
      face_detected    : bool
      gaze_off_center  : bool  (face center > 35% off image center)
      timestamp        : float
    """
    ts = time.time()

    img = _decode_image(image_bytes)
    if img is None:
        return {"face_detected": False, "error": "decode_failed", "timestamp": ts}

    img_h, img_w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Equalize histogram to handle varied lighting
    gray = cv2.equalizeHist(gray)

    cascade = _get_cascade()
    faces = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=3,
        minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )

    face_count = len(faces) if faces is not None and len(faces) > 0 else 0

    if face_count == 0:
        return {
            "dominant_emotion": "unknown",
            "emotion_scores": {},
            "face_count": 0,
            "face_detected": False,
            "gaze_off_center": False,
            "timestamp": ts,
        }

    # Gaze heuristic: primary face center more than 35% off image center
    x, y, w, h = faces[0]
    face_center_x = int(x) + int(w) / 2
    offset = abs(face_center_x - img_w / 2) / img_w
    gaze_off_center = bool(offset > 0.35)  # cast to Python bool — numpy.bool_ breaks FastAPI

    return {
        "dominant_emotion": "unknown",
        "emotion_scores": {},
        "face_count": int(face_count),
        "face_detected": True,
        "gaze_off_center": gaze_off_center,
        "timestamp": float(ts),
    }


def aggregate_face_frames(frames: list, alert_count: int = 0, clip_paths: list = None) -> dict:
    """
    Summarize per-frame results for one question into integrity metrics.
    """
    if not frames:
        return {
            "dominant_emotion": "unknown",
            "emotion_timeline": [],
            "integrity": {
                "multiple_faces_detected": False,
                "face_absent_pct": 0.0,
                "gaze_off_center_pct": 0.0,
                "alert_count": alert_count,
                "clip_paths": clip_paths or [],
                "suspicious": False,
            },
        }

    total = len(frames)
    detected = [f for f in frames if f.get("face_detected", False)]

    face_absent_pct = round((total - len(detected)) / total, 3)
    gaze_off_pct = round(
        sum(1 for f in detected if f.get("gaze_off_center", False)) / total, 3
    )
    multiple_faces = any(f.get("face_count", 0) > 1 for f in frames)

    suspicious = (
        multiple_faces
        or face_absent_pct > 0.20
        or gaze_off_pct > 0.30
    )

    timeline = [
        {
            "index": i,
            "emotion": f.get("dominant_emotion", "unknown"),
            "gaze_off": f.get("gaze_off_center", False),
        }
        for i, f in enumerate(frames)
    ]

    return {
        "dominant_emotion": "unknown",
        "emotion_timeline": timeline,
        "integrity": {
            "multiple_faces_detected": multiple_faces,
            "face_absent_pct": face_absent_pct,
            "gaze_off_center_pct": gaze_off_pct,
            "alert_count": alert_count,
            "clip_paths": clip_paths or [],
            "suspicious": suspicious,
        },
    }
