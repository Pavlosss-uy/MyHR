import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { analyzeFrame } from "@/lib/interviewApi";

/**
 * useProctoring — centralised proctoring logic for interview rooms.
 *
 * Replaces the inline proctoring useEffect that was duplicated in
 * InterviewRoom.jsx and CandidateInterviewPortal.jsx.
 *
 * Features:
 *   - Timestamped violation event log
 *   - Suspicion score (0–100) with decay
 *   - 5-tier warning escalation
 *   - Per-answer integrity aggregate
 *   - Configurable warning visibility
 *
 * @param {React.RefObject} videoRef   — ref to the <video> element
 * @param {React.RefObject} canvasRef  — ref to a hidden <canvas> for frame capture
 * @param {boolean}         isCameraOn — whether the camera is active
 * @param {string|null}     mediaError — error string if camera access failed
 * @param {object}          options    — { showWarnings: true, frameIntervalMs: 2000 }
 */

// ---------------------------------------------------------------------------
// Warning tier definitions
// ---------------------------------------------------------------------------
const WARNING_TIERS = [
    { min: 0,  max: 15, tier: 0, message: null },
    { min: 16, max: 35, tier: 1, message: "Please keep your attention on the screen." },
    { min: 36, max: 60, tier: 2, message: "Multiple attention lapses detected. This will be noted in your report." },
    { min: 61, max: 80, tier: 3, message: "Continued violations may affect your interview results." },
    { min: 81, max: 100, tier: 4, message: "Interview integrity at risk — please remain focused on the interview." },
];

// Suspicion score increments per violation type
const SCORE_INCREMENTS = {
    looking_away:      2,
    no_face:           4,
    multiple_faces:   10,
    camera_obstructed: 8,
    low_quality:       1,
};

// Max increment per single incident (prevents runaway scores from long violations)
const MAX_INCREMENT_PER_INCIDENT = {
    looking_away:      6,
    no_face:          12,
    camera_obstructed: 16,
    low_quality:       3,
};

// Decay: −1 point per this many seconds of clean behaviour
const DECAY_INTERVAL_S = 30;

// Sustained no_face threshold → camera_obstructed (in frames, at 2s intervals = 10s)
const CAMERA_OBSTRUCTED_FRAMES = 5;

function getTier(score) {
    for (const t of WARNING_TIERS) {
        if (score >= t.min && score <= t.max) return t;
    }
    return WARNING_TIERS[WARNING_TIERS.length - 1];
}

let _violationIdCounter = 0;
function nextViolationId() {
    _violationIdCounter += 1;
    return `v_${String(_violationIdCounter).padStart(3, "0")}`;
}

export function useProctoring(videoRef, canvasRef, isCameraOn, mediaError, options = {}) {
    const { showWarnings = true, frameIntervalMs = 2000 } = options;

    // --- State ---
    const [proctorAlert, setProctorAlert]       = useState(null);
    const [warningTier, setWarningTier]         = useState(0);
    const [warningMessage, setWarningMessage]   = useState(null);
    const [suspicionScore, setSuspicionScore]   = useState(0);
    const [violationCount, setViolationCount]   = useState(0);
    const [gazeScore, setGazeScore]             = useState(1.0);

    // --- Refs (mutable, no re-render) ---
    const frameBufferRef       = useRef([]);           // raw frame results for current answer
    const violationLogRef      = useRef([]);           // full session violation log
    const suspicionRef         = useRef(0);            // mirror of suspicionScore (avoidsclosure stale)
    const lastCleanTimeRef     = useRef(Date.now());   // last time with no violations
    const consecutiveNoFaceRef = useRef(0);            // for camera_obstructed detection
    const activeIncidentRef    = useRef(null);          // currently-ongoing violation { id, type, startTime, frames }
    const questionNumberRef    = useRef(1);

    // --- Update suspicion score (clamped 0-100) ---
    const adjustScore = useCallback((delta) => {
        suspicionRef.current = Math.max(0, Math.min(100, suspicionRef.current + delta));
        setSuspicionScore(suspicionRef.current);
        const t = getTier(suspicionRef.current);
        setWarningTier(t.tier);
        setWarningMessage(showWarnings ? t.message : null);
    }, [showWarnings]);

    // --- Close active incident ---
    const closeIncident = useCallback(() => {
        const incident = activeIncidentRef.current;
        if (incident) {
            incident.endTime = Date.now() / 1000;
            incident.duration_ms = Math.round((incident.endTime - incident.startTime) * 1000);
            violationLogRef.current.push({ ...incident });
            activeIncidentRef.current = null;
        }
    }, []);

    // --- Start or extend an incident ---
    const handleViolation = useCallback((type, severity, result) => {
        const active = activeIncidentRef.current;
        if (active && active.type === type) {
            // Extend existing incident
            active.frames += 1;
            const maxInc = MAX_INCREMENT_PER_INCIDENT[type] || 10;
            const inc = SCORE_INCREMENTS[type] || 2;
            if (active.frames * inc <= maxInc) {
                adjustScore(inc);
            }
            // Track worst gaze during incident
            if (result.gaze_score != null && result.gaze_score < (active.worst_gaze ?? 1.0)) {
                active.worst_gaze = result.gaze_score;
            }
        } else {
            // Close previous incident if different type
            closeIncident();
            // Start new incident
            const inc = SCORE_INCREMENTS[type] || 2;
            adjustScore(inc);
            activeIncidentRef.current = {
                id: nextViolationId(),
                type,
                severity,
                startTime: Date.now() / 1000,
                endTime: null,
                duration_ms: 0,
                question_number: questionNumberRef.current,
                worst_gaze: result.gaze_score ?? 1.0,
                frames: 1,
            };
            setViolationCount((c) => c + 1);
        }
    }, [adjustScore, closeIncident]);

    // --- Process a single frame result ---
    const processFrame = useCallback((result) => {
        frameBufferRef.current.push(result);

        // Update live gaze score
        if (result.gaze_score != null) {
            setGazeScore(result.gaze_score);
        }

        // Determine violation type (most severe first)
        if (result.multiple_faces) {
            consecutiveNoFaceRef.current = 0;
            handleViolation("multiple_faces", "high", result);
            setProctorAlert("multiple");
        } else if (!result.face_present) {
            consecutiveNoFaceRef.current += 1;
            if (consecutiveNoFaceRef.current >= CAMERA_OBSTRUCTED_FRAMES) {
                handleViolation("camera_obstructed", "high", result);
            } else {
                handleViolation("no_face", "medium", result);
            }
            setProctorAlert("no_face");
        } else if (result.looking_away) {
            consecutiveNoFaceRef.current = 0;
            handleViolation("looking_away", "low", result);
            setProctorAlert("looking_away");
        } else if (result.low_quality) {
            consecutiveNoFaceRef.current = 0;
            handleViolation("low_quality", "low", result);
            setProctorAlert(null); // Don't show low_quality as a user-facing alert
        } else {
            // Clean frame — close any active incident, apply decay
            consecutiveNoFaceRef.current = 0;
            closeIncident();
            setProctorAlert(null);

            // Decay: compare against the time we last had a clean frame
            const elapsed = (Date.now() - lastCleanTimeRef.current) / 1000;
            if (elapsed >= DECAY_INTERVAL_S) {
                adjustScore(-1);
                lastCleanTimeRef.current = Date.now();
            }
            // NOTE: do NOT reset lastCleanTimeRef here every clean frame — that
            // would always make elapsed ≈ 0 and prevent decay from ever firing.
        }
    }, [handleViolation, closeIncident, adjustScore]);

    // --- Frame capture interval ---
    useEffect(() => {
        if (!isCameraOn || mediaError) return;

        const interval = setInterval(async () => {
            const video  = videoRef.current;
            const canvas = canvasRef.current;
            if (!video || !canvas || video.readyState < 2) return;

            canvas.width  = 640;
            canvas.height = 480;
            canvas.getContext("2d").drawImage(video, 0, 0, 640, 480);
            const base64 = canvas.toDataURL("image/jpeg", 0.75).split(",")[1];

            try {
                const result = await analyzeFrame(base64);
                processFrame(result);
            } catch {
                /* silent — network error should not crash the interview */
            }
        }, frameIntervalMs);

        return () => clearInterval(interval);
    }, [isCameraOn, mediaError, frameIntervalMs, processFrame]);

    // --- Per-answer integrity aggregate ---
    const getAnswerIntegrity = useCallback(() => {
        const frames = frameBufferRef.current;
        if (!frames || frames.length === 0) {
            return {
                face_absent_pct: 0,
                looking_away_pct: 0,
                multiple_faces_detected: false,
                frames_analyzed: 0,
                suspicious: false,
                violation_count: 0,
                avg_gaze_score: 1.0,
                min_gaze_score: 1.0,
                suspicion_score: suspicionRef.current,
            };
        }

        const total   = frames.length;
        const present = frames.filter((f) => f.face_present);
        const faceAbsentPct   = +((total - present.length) / total).toFixed(3);
        const lookingAwayPct  = +(present.filter((f) => f.looking_away).length / total).toFixed(3);
        const multipleFaces   = frames.some((f) => f.multiple_faces);

        // Gaze stats
        const gazeScores = present
            .filter((f) => f.gaze_score != null)
            .map((f) => f.gaze_score);
        const avgGaze = gazeScores.length > 0
            ? +(gazeScores.reduce((a, b) => a + b, 0) / gazeScores.length).toFixed(3)
            : 1.0;
        const minGaze = gazeScores.length > 0
            ? +Math.min(...gazeScores).toFixed(3)
            : 1.0;

        // Count violations in this answer window
        const answerViolations = violationLogRef.current.filter(
            (v) => v.question_number === questionNumberRef.current
        ).length;

        return {
            face_absent_pct: faceAbsentPct,
            looking_away_pct: lookingAwayPct,
            multiple_faces_detected: multipleFaces,
            frames_analyzed: total,
            suspicious: multipleFaces || faceAbsentPct > 0.20 || lookingAwayPct > 0.30,
            violation_count: answerViolations,
            avg_gaze_score: avgGaze,
            min_gaze_score: minGaze,
            suspicion_score: suspicionRef.current,
        };
    }, []);

    // --- Reset buffer between answers ---
    const resetAnswerBuffer = useCallback(() => {
        // Close any dangling incident
        closeIncident();
        frameBufferRef.current = [];
        questionNumberRef.current += 1;
    }, [closeIncident]);

    // --- Set question number (for correlation) ---
    const setQuestionNumber = useCallback((n) => {
        questionNumberRef.current = n;
    }, []);

    // --- Full violation log (for submit to backend) ---
    const violationLog = useMemo(() => violationLogRef.current, [violationCount]);

    return {
        // Live UI state
        proctorAlert,
        warningTier,
        warningMessage,
        suspicionScore,
        gazeScore,
        violationCount,

        // Data accessors
        violationLog,
        getAnswerIntegrity,
        resetAnswerBuffer,
        setQuestionNumber,
    };
}
