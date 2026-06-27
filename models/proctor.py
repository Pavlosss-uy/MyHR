"""Proctoring — integrity analysis for interview video frames.

Detects cheating signals for the AI interview platform:

  - out-of-frame     : no face visible
  - multiple people   : more than one face in frame
  - looking-away      : true eye-gaze detection via iris tracking + head pose
  - camera obstructed : sustained face absence (> threshold)
  - low quality       : poor lighting or blurry frame

Detection pipeline
------------------
1. **YuNet** (cv2.FaceDetectorYN) — fast ONNX face detector for face count and
   bounding boxes. Used as a pre-filter for multi-face detection.

2. **MediaPipe FaceMesh** (with `refine_landmarks=True`) — provides 478
   landmarks including iris contours (landmarks 468-477). From these we compute:
   - **Iris Position Ratio (IPR)**: horizontal iris center position relative to
     eye corners. Detects looking at a second monitor even when the head is
     perfectly still.
   - **Eye Aspect Ratio (EAR)**: detects closed eyes, extreme downward gaze,
     or squinting.
   - **Head pose**: nose-to-eye-midline yaw + vertical foreshortening.

3. Fallback chain: MediaPipe → YuNet-only head-pose → Haar cascade.

Runs synchronously; callers must wrap in ``asyncio.to_thread`` so the FastAPI
event loop is never blocked. A lock serializes access to the shared detectors.
"""

import logging
import os
import time
import threading

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
_YUNET_PATH = os.path.join(os.path.dirname(__file__), "weights", "face_detection_yunet_2023mar.onnx")

# YuNet
_SCORE_THRESHOLD = 0.70          # face-confidence floor

# Head-pose thresholds (YuNet-only fallback)
_YAW_THRESHOLD = 0.25
_VSPAN_MIN = 0.75
_VSPAN_MAX = 1.45
_GAZE_OFFSET_THRESHOLD = 0.35   # Haar fallback

# MediaPipe iris thresholds
_IPR_CENTER_MIN = 0.30           # iris ratio below this → looking left/right
_IPR_CENTER_MAX = 0.70           # iris ratio above this → looking left/right
_EAR_CLOSED_THRESHOLD = 0.18    # below this → eye closed or extreme downward
_GAZE_SCORE_WEIGHTS = {
    "iris": 0.55,                # iris position contribution to gaze_score
    "head": 0.45,                # head pose contribution to gaze_score
}

# Low quality detection
_LOW_QUALITY_BRIGHTNESS_MIN = 40   # mean pixel brightness below this = too dark
_LOW_QUALITY_BRIGHTNESS_MAX = 240  # mean pixel brightness above this = overexposed
_LOW_QUALITY_LAPLACIAN_MIN = 30    # Laplacian variance below this = blurry

# ---------------------------------------------------------------------------
# Singleton detectors
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_yunet = None
_yunet_failed = False
_haar = None
_face_mesh = None
_face_mesh_failed = False


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


def _get_face_mesh():
    """Lazy-load MediaPipe FaceMesh with iris refinement."""
    global _face_mesh, _face_mesh_failed
    if _face_mesh is not None:
        return _face_mesh
    if _face_mesh_failed:
        return None
    try:
        import mediapipe as mp
        _face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,   # enables iris landmarks (468-477)
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return _face_mesh
    except ImportError:
        logger.warning("[WARN] MediaPipe not installed — falling back to YuNet head-pose only.")
        _face_mesh_failed = True
        return None
    except Exception as e:
        logger.warning("[WARN] MediaPipe FaceMesh init failed (%s) — falling back to YuNet.", e)
        _face_mesh_failed = True
        return None


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------
def _empty_result(ts: float) -> dict:
    return {
        "face_count": 0,
        "face_present": False,
        "multiple_faces": False,
        "looking_away": False,
        "gaze_score": 0.0,
        "head_yaw": 0.0,
        "head_vspan": 0.0,
        "iris_offset": None,
        "detection_confidence": 0.0,
        "low_quality": False,
        "timestamp": ts,
    }


# ---------------------------------------------------------------------------
# Image quality assessment
# ---------------------------------------------------------------------------
def _assess_quality(img_bgr) -> bool:
    """Return True if the frame is low quality (too dark, too bright, or blurry)."""
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))
        if mean_brightness < _LOW_QUALITY_BRIGHTNESS_MIN or mean_brightness > _LOW_QUALITY_BRIGHTNESS_MAX:
            return True
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if laplacian_var < _LOW_QUALITY_LAPLACIAN_MIN:
            return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# MediaPipe iris-based gaze detection
# ---------------------------------------------------------------------------

# MediaPipe FaceMesh landmark indices for iris analysis
# Left eye corners: 33 (outer), 133 (inner); Left iris center: 468
# Right eye corners: 362 (outer), 263 (inner); Right iris center: 473
# EAR landmarks: left eye vertical: (159, 145), (158, 153); right eye: (386, 374), (385, 380)
_LEFT_EYE_OUTER = 33
_LEFT_EYE_INNER = 133
_LEFT_IRIS_CENTER = 468
_RIGHT_EYE_OUTER = 362
_RIGHT_EYE_INNER = 263
_RIGHT_IRIS_CENTER = 473

# EAR (Eye Aspect Ratio) landmarks
_LEFT_EYE_TOP = [159, 158]
_LEFT_EYE_BOTTOM = [145, 153]
_RIGHT_EYE_TOP = [386, 385]
_RIGHT_EYE_BOTTOM = [374, 380]
_LEFT_EYE_H = [33, 133]   # horizontal span
_RIGHT_EYE_H = [362, 263]

# Head pose landmarks
_NOSE_TIP = 1
_LEFT_EYE_MESH = 468    # iris center (with refinement)
_RIGHT_EYE_MESH = 473
_MOUTH_LEFT = 61
_MOUTH_RIGHT = 291


def _compute_ipr(landmarks, img_w: int) -> tuple:
    """Compute Iris Position Ratio for both eyes.

    Returns (left_ipr, right_ipr, avg_ipr).
    IPR = 0.0 means iris at outer corner, 1.0 = inner corner.
    Centered gaze ≈ 0.4–0.6.
    """
    def _eye_ipr(outer_idx, inner_idx, iris_idx):
        outer = np.array([landmarks[outer_idx].x, landmarks[outer_idx].y])
        inner = np.array([landmarks[inner_idx].x, landmarks[inner_idx].y])
        iris = np.array([landmarks[iris_idx].x, landmarks[iris_idx].y])
        eye_width = float(np.linalg.norm(inner - outer))
        if eye_width < 1e-6:
            return 0.5
        iris_dist = float(np.linalg.norm(iris - outer))
        return min(1.0, max(0.0, iris_dist / eye_width))

    left_ipr = _eye_ipr(_LEFT_EYE_OUTER, _LEFT_EYE_INNER, _LEFT_IRIS_CENTER)
    right_ipr = _eye_ipr(_RIGHT_EYE_OUTER, _RIGHT_EYE_INNER, _RIGHT_IRIS_CENTER)
    avg_ipr = (left_ipr + right_ipr) / 2.0
    return left_ipr, right_ipr, avg_ipr


def _compute_ear(landmarks) -> float:
    """Compute average Eye Aspect Ratio (EAR) for both eyes.

    Low EAR = eye closed or extreme downward gaze.
    Normal open eye ≈ 0.25–0.35.
    """
    def _eye_ear(top_indices, bottom_indices, h_indices):
        v_dists = []
        for t_idx, b_idx in zip(top_indices, bottom_indices):
            top = np.array([landmarks[t_idx].x, landmarks[t_idx].y])
            bottom = np.array([landmarks[b_idx].x, landmarks[b_idx].y])
            v_dists.append(float(np.linalg.norm(top - bottom)))
        h_left = np.array([landmarks[h_indices[0]].x, landmarks[h_indices[0]].y])
        h_right = np.array([landmarks[h_indices[1]].x, landmarks[h_indices[1]].y])
        h_dist = float(np.linalg.norm(h_left - h_right))
        if h_dist < 1e-6:
            return 0.3  # default
        return sum(v_dists) / (len(v_dists) * h_dist)

    left_ear = _eye_ear(_LEFT_EYE_TOP, _LEFT_EYE_BOTTOM, _LEFT_EYE_H)
    right_ear = _eye_ear(_RIGHT_EYE_TOP, _RIGHT_EYE_BOTTOM, _RIGHT_EYE_H)
    return (left_ear + right_ear) / 2.0


def _head_pose_from_mesh(landmarks) -> tuple:
    """Estimate head yaw and vertical span from MediaPipe FaceMesh landmarks.

    Returns (yaw: float, vspan: float).
    """
    # Use nose tip and eye iris centers for pose
    nose = np.array([landmarks[_NOSE_TIP].x, landmarks[_NOSE_TIP].y])
    left_eye = np.array([landmarks[_LEFT_EYE_MESH].x, landmarks[_LEFT_EYE_MESH].y])
    right_eye = np.array([landmarks[_RIGHT_EYE_MESH].x, landmarks[_RIGHT_EYE_MESH].y])
    mouth_left = np.array([landmarks[_MOUTH_LEFT].x, landmarks[_MOUTH_LEFT].y])
    mouth_right = np.array([landmarks[_MOUTH_RIGHT].x, landmarks[_MOUTH_RIGHT].y])

    eye_mid = (left_eye + right_eye) / 2.0
    mouth_mid = (mouth_left + mouth_right) / 2.0
    inter_ocular = float(np.linalg.norm(right_eye - left_eye))
    if inter_ocular < 1e-6:
        return 0.0, 1.0

    yaw = abs(float(nose[0] - eye_mid[0])) / inter_ocular
    vspan = abs(float(mouth_mid[1] - eye_mid[1])) / inter_ocular
    return round(yaw, 3), round(vspan, 3)


def _compute_gaze_score(ipr: float, yaw: float, vspan: float, ear: float) -> float:
    """Compute a combined gaze score (0.0 = looking away, 1.0 = looking at camera).

    Blends iris-based and head-pose signals.
    """
    # Iris component: how centered is the iris? (0.5 = perfect center)
    iris_deviation = abs(ipr - 0.5) / 0.5  # 0.0 = centered, 1.0 = extreme
    iris_score = max(0.0, 1.0 - iris_deviation * 2.0)

    # Head component: how straight is the head?
    head_yaw_score = max(0.0, 1.0 - yaw / 0.5)  # 0.5 yaw = fully turned
    head_vspan_ok = 1.0 if _VSPAN_MIN <= vspan <= _VSPAN_MAX else max(0.0, 0.5)
    head_score = head_yaw_score * head_vspan_ok

    # EAR penalty: closed eyes reduce gaze_score
    ear_factor = 1.0 if ear >= _EAR_CLOSED_THRESHOLD else 0.3

    # Weighted blend
    w = _GAZE_SCORE_WEIGHTS
    raw = w["iris"] * iris_score + w["head"] * head_score
    return round(max(0.0, min(1.0, raw * ear_factor)), 3)


def _analyze_mediapipe(img_bgr, face_count: int, detection_confidence: float, ts: float) -> dict | None:
    """Analyze a single frame using MediaPipe FaceMesh for gaze detection.

    Returns None if MediaPipe is unavailable (caller falls back to YuNet-only).
    """
    mesh = _get_face_mesh()
    if mesh is None:
        return None

    # MediaPipe expects RGB
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    with _lock:
        results = mesh.process(img_rgb)

    if not results.multi_face_landmarks:
        return _empty_result(ts)

    landmarks = results.multi_face_landmarks[0].landmark

    # Iris Position Ratio
    _, _, avg_ipr = _compute_ipr(landmarks, img_bgr.shape[1])

    # Eye Aspect Ratio
    ear = _compute_ear(landmarks)

    # Head pose from mesh landmarks
    yaw, vspan = _head_pose_from_mesh(landmarks)

    # Combined gaze score
    gaze_score = _compute_gaze_score(avg_ipr, yaw, vspan, ear)

    # Looking-away decision: iris off-center OR head turned OR eyes closed
    iris_off = avg_ipr < _IPR_CENTER_MIN or avg_ipr > _IPR_CENTER_MAX
    head_turned = yaw > _YAW_THRESHOLD or vspan < _VSPAN_MIN or vspan > _VSPAN_MAX
    eyes_closed = ear < _EAR_CLOSED_THRESHOLD
    looking_away = bool(iris_off or head_turned or eyes_closed)

    return {
        "face_count": face_count,
        "face_present": True,
        "multiple_faces": bool(face_count > 1),
        "looking_away": looking_away,
        "gaze_score": gaze_score,
        "head_yaw": yaw,
        "head_vspan": vspan,
        "iris_offset": round(avg_ipr, 3),
        "ear": round(ear, 3),
        "detection_confidence": round(detection_confidence, 3),
        "low_quality": False,   # set by caller
        "timestamp": float(ts),
    }


# ---------------------------------------------------------------------------
# YuNet head-pose (fallback when MediaPipe unavailable)
# ---------------------------------------------------------------------------
def _head_pose_from_landmarks(face_row):
    """Estimate head pose from YuNet's 5 landmarks.

    Returns (looking_away: bool, yaw: float, vspan: float).
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

    yaw = abs(float(nose[0] - eye_mid[0])) / inter_ocular
    vspan = abs(float(mouth_mid[1] - eye_mid[1])) / inter_ocular

    looking_away = bool(yaw > _YAW_THRESHOLD or vspan < _VSPAN_MIN or vspan > _VSPAN_MAX)
    return looking_away, round(yaw, 3), round(vspan, 3)


def _analyze_yunet_only(img_bgr, ts: float) -> dict | None:
    """YuNet-only analysis (head-pose, no iris tracking)."""
    detector = _get_yunet()
    if detector is None:
        return None

    img_h, img_w = img_bgr.shape[:2]
    with _lock:
        detector.setInputSize((img_w, img_h))
        _, faces = detector.detect(img_bgr)

    if faces is None or len(faces) == 0:
        return _empty_result(ts)

    face_count = len(faces)
    primary = max(faces, key=lambda f: float(f[14]))
    confidence = float(primary[14])
    looking_away, yaw, vspan = _head_pose_from_landmarks(primary)

    # Approximate gaze_score from head-pose only (no iris data)
    head_yaw_score = max(0.0, 1.0 - yaw / 0.5)
    head_vspan_ok = 1.0 if _VSPAN_MIN <= vspan <= _VSPAN_MAX else 0.5
    gaze_score = round(head_yaw_score * head_vspan_ok, 3)

    return {
        "face_count": int(face_count),
        "face_present": True,
        "multiple_faces": bool(face_count > 1),
        "looking_away": looking_away,
        "gaze_score": gaze_score,
        "head_yaw": yaw,
        "head_vspan": vspan,
        "iris_offset": None,   # not available without MediaPipe
        "detection_confidence": round(confidence, 3),
        "low_quality": False,
        "timestamp": float(ts),
    }


def _analyze_haar(img_bgr, ts: float) -> dict:
    """Haar cascade fallback (bounding box only, no landmarks)."""
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
    looking_away = bool(offset > _GAZE_OFFSET_THRESHOLD)
    gaze_score = round(max(0.0, 1.0 - offset * 2.0), 3)

    return {
        "face_count": int(face_count),
        "face_present": True,
        "multiple_faces": bool(face_count > 1),
        "looking_away": looking_away,
        "gaze_score": gaze_score,
        "head_yaw": 0.0,
        "head_vspan": 0.0,
        "iris_offset": None,
        "detection_confidence": 0.5,   # Haar doesn't provide confidence
        "low_quality": False,
        "timestamp": float(ts),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def warmup() -> None:
    """Load detectors once at startup so the first frame is fast."""
    try:
        mesh = _get_face_mesh()
        if mesh is not None:
            logger.info("[OK]   Proctor ready (MediaPipe FaceMesh with iris tracking).")
        elif _get_yunet() is not None:
            logger.info("[OK]   Proctor ready (YuNet head-pose only — no iris tracking).")
        else:
            _get_haar()
            logger.warning("[WARN] YuNet model missing — proctor using Haar fallback (no gaze detection).")
    except Exception as e:
        logger.warning("[WARN] Proctor warmup skipped (%s).", e)


def analyze(img_bgr) -> dict:
    """Analyze one BGR frame (OpenCV ndarray) for proctoring signals.

    Uses a cascade of detectors:
      1. YuNet for fast face count
      2. MediaPipe FaceMesh for iris-based gaze on the primary face
      3. Falls back to YuNet-only head-pose if MediaPipe unavailable
      4. Falls back to Haar if YuNet model missing
    """
    ts = time.time()
    if img_bgr is None:
        return _empty_result(ts)

    try:
        # Assess image quality
        low_quality = _assess_quality(img_bgr)

        # Step 1: YuNet for fast face count
        face_count = 0
        detection_confidence = 0.0
        detector = _get_yunet()
        if detector is not None:
            img_h, img_w = img_bgr.shape[:2]
            with _lock:
                detector.setInputSize((img_w, img_h))
                _, faces = detector.detect(img_bgr)
            if faces is not None and len(faces) > 0:
                face_count = len(faces)
                detection_confidence = float(max(faces, key=lambda f: float(f[14]))[14])

        # Step 2: Try MediaPipe for iris-based gaze
        result = _analyze_mediapipe(img_bgr, face_count, detection_confidence, ts)

        # Step 3: Fall back to YuNet-only head-pose
        if result is None:
            result = _analyze_yunet_only(img_bgr, ts)

        # Step 4: Fall back to Haar
        if result is None:
            result = _analyze_haar(img_bgr, ts)

        # Overlay quality assessment
        result["low_quality"] = low_quality

        # If face was detected but quality is poor, reduce confidence in the result
        if low_quality and result.get("face_present"):
            result["detection_confidence"] = min(
                result.get("detection_confidence", 0.5), 0.4
            )

        return result

    except Exception as e:
        res = _empty_result(ts)
        res["error"] = str(e)
        return res


def aggregate(frames: list) -> dict:
    """Roll up per-frame results for one answer into an integrity summary.

    Enhanced with violation counts, severity classification, and gaze statistics.
    """
    if not frames:
        return {
            "face_absent_pct": 0.0,
            "looking_away_pct": 0.0,
            "multiple_faces_detected": False,
            "frames_analyzed": 0,
            "suspicious": False,
            "violation_count": 0,
            "avg_gaze_score": 1.0,
            "min_gaze_score": 1.0,
            "low_quality_pct": 0.0,
            "max_severity": "none",
        }

    total = len(frames)
    present = [f for f in frames if f.get("face_present", False)]
    face_absent_pct = round((total - len(present)) / total, 3)
    looking_away_frames = [f for f in present if f.get("looking_away", False)]
    looking_away_pct = round(len(looking_away_frames) / total, 3)
    multiple_faces = any(f.get("multiple_faces", False) for f in frames)
    low_quality_pct = round(
        sum(1 for f in frames if f.get("low_quality", False)) / total, 3
    )

    # Gaze statistics
    gaze_scores = [f.get("gaze_score", 1.0) for f in present if "gaze_score" in f]
    avg_gaze = round(sum(gaze_scores) / len(gaze_scores), 3) if gaze_scores else 1.0
    min_gaze = round(min(gaze_scores), 3) if gaze_scores else 1.0

    # Count distinct violations (not just flagged frames)
    violation_count = 0
    if multiple_faces:
        violation_count += sum(1 for f in frames if f.get("multiple_faces", False))
    violation_count += len(looking_away_frames)
    violation_count += sum(1 for f in frames if not f.get("face_present", True))

    # Severity classification
    if multiple_faces:
        max_severity = "high"
    elif face_absent_pct > 0.40 or looking_away_pct > 0.50:
        max_severity = "high"
    elif face_absent_pct > 0.20 or looking_away_pct > 0.30:
        max_severity = "medium"
    elif violation_count > 0:
        max_severity = "low"
    else:
        max_severity = "none"

    suspicious = bool(
        multiple_faces or face_absent_pct > 0.20 or looking_away_pct > 0.30
    )

    return {
        "face_absent_pct": face_absent_pct,
        "looking_away_pct": looking_away_pct,
        "multiple_faces_detected": multiple_faces,
        "frames_analyzed": total,
        "suspicious": suspicious,
        "violation_count": violation_count,
        "avg_gaze_score": avg_gaze,
        "min_gaze_score": min_gaze,
        "low_quality_pct": low_quality_pct,
        "max_severity": max_severity,
    }
