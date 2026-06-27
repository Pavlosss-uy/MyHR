import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import CameraFeed from "@/components/CameraFeed";
import VoiceWaveform from "@/components/VoiceWaveform";
import AudioQuestionPlayer from "@/components/AudioQuestionPlayer";
import { useMediaDevices } from "@/hooks/useMediaDevices";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { useProctoring } from "@/hooks/useProctoring";
import { useVAD } from "@/hooks/useVAD";
import { toast } from "sonner";
import {
    validateInterviewToken,
    completeCandidateInterview,
    startInterviewFromToken,
    submitAnswer,
    analyzeFrame,
} from "@/lib/interviewApi";
import {
    Brain,
    Mic,
    MicOff,
    Camera,
    CameraOff,
    CheckCircle2,
    Loader2,
    AlertCircle,
    Clock,
    PhoneOff,
    Send,
    MessageSquare,
    ArrowRight,
} from "lucide-react";

/**
 * Public candidate interview portal — token-based, no auth required.
 *
 * Design constraints:
 *  - NO score, rating, or per-question feedback shown to the candidate.
 *  - Proctoring runs silently; alerts are NOT surfaced to the candidate.
 *  - Completion navigates to a thank-you screen, NOT a feedback report.
 *
 * Architecture: The outer component handles phases (loading/welcome/completed/error).
 * The inner EnterpriseInterviewRoom mounts ONLY during the interview, which lets
 * useMediaDevices and useVAD request permissions at the right moment (after the
 * user has clicked "Begin Interview") rather than on the welcome screen.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Inner component — mounts only when interview is active
// Uses the same hooks as InterviewRoom so camera/VAD/mic behave identically.
// ─────────────────────────────────────────────────────────────────────────────
const EnterpriseInterviewRoom = ({
    token,
    sessionId,
    initialQuestion,
    initialAudioUrl,
    maxQuestionsInit,
    onComplete,
}) => {
    // ── Media devices (requests camera+mic on mount — correct here) ──────────
    const {
        videoRef, stream, audioStream,
        isCameraOn, isMicOn,
        toggleCamera, toggleMic,
        error: mediaError,
    } = useMediaDevices();

    const { isRecording, startRecording, stopRecording } = useAudioRecorder(stream);
    const { isPlaying, speakQuestion, stopSpeaking }     = useAudioPlayer();

    // ── VAD countdown state (defined before useVAD so setters are stable) ────
    const [preAnswerCountdown, setPreAnswerCountdown] = useState(null); // 3|2|1|null
    const [noSpeechTimer,      setNoSpeechTimer]      = useState(null); // 45→0|null
    const [pendingBlob,        setPendingBlob]         = useState(null);
    const [silenceCountdown,   setSilenceCountdown]   = useState(null); // 3|2|1|0|null
    const hasSpokeRef   = useRef(false);
    const wasPlayingRef = useRef(false);

    const { vadBlob, clearBlob, userSpeaking: vadSpeaking, listening: vadListening, setVADPaused } = useVAD({
        onSpeechStart: () => {
            hasSpokeRef.current = true;
            setNoSpeechTimer(null);
            setSilenceCountdown(null);
            setPendingBlob(null);
        },
    });

    // ── Interview state ──────────────────────────────────────────────────────
    const [currentQuestion, setCurrentQuestion] = useState(initialQuestion);
    const [audioUrl,        setAudioUrl]        = useState(initialAudioUrl);
    const [questionNumber,  setQuestionNumber]  = useState(1);
    const [maxQuestions,    setMaxQuestions]    = useState(maxQuestionsInit);
    const [messages,        setMessages]        = useState([{ role: "ai", text: initialQuestion }]);
    const [isSubmitting,    setIsSubmitting]    = useState(false);
    const [isEnding,        setIsEnding]        = useState(false);
    const [submitError,     setSubmitError]     = useState("");

    // ── Timers ───────────────────────────────────────────────────────────────
    const [elapsed,          setElapsed]          = useState(0);
    const [recordingElapsed, setRecordingElapsed] = useState(0);

    // ── Backend TTS audio ────────────────────────────────────────────────────
    const audioRef = useRef(null);
    const [isBackendPlaying, setIsBackendPlaying] = useState(false);

    // ── Proctoring (centralised hook) ────────────────────────────────────────
    const canvasRef = useRef(null);
    const {
        proctorAlert,
        warningTier,
        warningMessage,
        suspicionScore,
        gazeScore,
        violationCount,
        violationLog,
        getAnswerIntegrity,
        resetAnswerBuffer,
        setQuestionNumber: setProctoringQuestion,
    } = useProctoring(videoRef, canvasRef, isCameraOn, mediaError, { showWarnings: true });

    // Sync question number with proctoring
    useEffect(() => {
        setProctoringQuestion(questionNumber);
    }, [questionNumber, setProctoringQuestion]);

    // ── Refs ─────────────────────────────────────────────────────────────────
    const transcriptRef       = useRef(null);
    const evaluationsRef      = useRef([]);
    const currentQuestionRef  = useRef(initialQuestion);

    const fmt = (secs) => {
        const m = Math.floor(secs / 60).toString().padStart(2, "0");
        const s = (secs % 60).toString().padStart(2, "0");
        return `${m}:${s}`;
    };

    useEffect(() => { currentQuestionRef.current = currentQuestion; }, [currentQuestion]);

    // ── Timers ───────────────────────────────────────────────────────────────
    useEffect(() => {
        const t = setInterval(() => setElapsed((s) => s + 1), 1000);
        return () => clearInterval(t);
    }, []);

    useEffect(() => {
        let t;
        if (isRecording) {
            t = setInterval(() => setRecordingElapsed((s) => s + 1), 1000);
        } else {
            setRecordingElapsed(0);
        }
        return () => clearInterval(t);
    }, [isRecording]);

    // ── Auto-scroll transcript ───────────────────────────────────────────────
    useEffect(() => {
        if (transcriptRef.current) {
            transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
        }
    }, [messages]);

    // ── Auto-play TTS when question changes ─────────────────────────────────
    useEffect(() => {
        if (!currentQuestion) return;
        stopSpeaking();
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            setIsBackendPlaying(false);
        }
        if (audioUrl && audioRef.current) {
            audioRef.current.src = audioUrl;
            audioRef.current.play().catch(() => speakQuestion(currentQuestion));
        } else {
            const id = setTimeout(() => speakQuestion(currentQuestion), 500);
            return () => clearTimeout(id);
        }
    }, [audioUrl, currentQuestion]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Mute VAD while TTS playing; start pre-answer countdown when it ends ──
    useEffect(() => {
        const ttsActive = isBackendPlaying || isPlaying;
        if (ttsActive) {
            wasPlayingRef.current = true;
            setVADPaused(true);
            setPreAnswerCountdown(null);
            setSilenceCountdown(null);
            setPendingBlob(null);
        } else if (wasPlayingRef.current) {
            wasPlayingRef.current = false;
            // Show "Get ready" countdown; VAD stays paused until countdown hits 0
            setPreAnswerCountdown(3);
        }
    }, [isBackendPlaying, isPlaying]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Pre-answer countdown: 3→2→1→0 → enable VAD + start anti-cheat timer ─
    useEffect(() => {
        if (preAnswerCountdown === null) return;
        if (preAnswerCountdown === 0) {
            setPreAnswerCountdown(null);
            setVADPaused(false);
            hasSpokeRef.current = false;
            setNoSpeechTimer(45);
            return;
        }
        const t = setTimeout(() => setPreAnswerCountdown((c) => c - 1), 1000);
        return () => clearTimeout(t);
    }, [preAnswerCountdown]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Anti-cheat: auto-submit empty if candidate stays silent for 45s ──────
    useEffect(() => {
        if (noSpeechTimer === null) return;
        if (noSpeechTimer === 0) {
            setNoSpeechTimer(null);
            if (!isSubmitting && sessionId)
                _doSubmit(new Blob([], { type: "audio/wav" }));
            return;
        }
        const t = setTimeout(() => setNoSpeechTimer((c) => c - 1), 1000);
        return () => clearTimeout(t);
    }, [noSpeechTimer]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Proctoring frame capture is now handled by useProctoring ────────────

    // ── Core submit ──────────────────────────────────────────────────────────
    const _doSubmit = useCallback(async (audioBlob) => {
        setIsSubmitting(true);
        setSubmitError("");
        stopSpeaking();
        if (audioRef.current) { audioRef.current.pause(); setIsBackendPlaying(false); }

        const integrity = getAnswerIntegrity();
        resetAnswerBuffer();

        try {
            const result = await submitAnswer(sessionId, audioBlob, integrity);

            if (result.transcription) {
                setMessages((prev) => [...prev, { role: "user", text: result.transcription }]);
            }

            if (result.status === "retry") {
                setSubmitError(result.message || "Didn't catch that — please answer again.");
                return;
            }

            // Accumulate evaluations (score is never shown to candidate)
            evaluationsRef.current = [
                ...evaluationsRef.current,
                {
                    question: currentQuestionRef.current,
                    answer:   result.transcription || "",
                    score:    result.feedback?.score || 0,
                },
            ];

            if (result.status === "completed" || questionNumber >= maxQuestions) {
                const closing = result.closing_message
                    || "Thank you for completing the interview. Your responses have been submitted to the hiring team.";
                setMessages((prev) => [...prev, { role: "ai", text: closing }]);

                // Persist to Firestore (fire-and-forget — error is non-fatal)
                try {
                    const evals    = evaluationsRef.current;
                    const avgScore = evals.length > 0
                        ? evals.reduce((s, e) => s + (e.score || 0), 0) / evals.length
                        : 0;
                    await completeCandidateInterview(token, sessionId, avgScore, {
                        evaluations: evals,
                        summary:    result.rich_report?.summary    || "",
                        strengths:  result.rich_report?.strengths  || [],
                        weaknesses: result.rich_report?.weaknesses || [],
                    }, violationLog);
                } catch (e) {
                    console.error("Failed to save interview results:", e);
                }

                // Play closing TTS, then hand off to outer component
                const estimatedMs = Math.min(10000, Math.max(3000, closing.length * 55));
                let done = false;
                const goComplete = () => { if (done) return; done = true; onComplete(); };

                if (result.closing_audio_url && audioRef.current) {
                    const cap = setTimeout(goComplete, 12000);
                    audioRef.current.onended = () => { clearTimeout(cap); setTimeout(goComplete, 600); };
                    audioRef.current.onerror = () => { clearTimeout(cap); speakQuestion(closing); setTimeout(goComplete, estimatedMs); };
                    audioRef.current.src = result.closing_audio_url;
                    audioRef.current.play().catch(() => { clearTimeout(cap); speakQuestion(closing); setTimeout(goComplete, estimatedMs); });
                } else {
                    speakQuestion(closing);
                    setTimeout(goComplete, estimatedMs);
                }
            } else {
                const nextQ = result.next_question || result.question || "";
                setCurrentQuestion(nextQ);
                setAudioUrl(result.audio_url || null);
                if (result.question_number != null) setQuestionNumber(result.question_number);
                else setQuestionNumber((n) => n + 1);
                if (result.max_questions != null) setMaxQuestions(result.max_questions);
                setMessages((prev) => [...prev, { role: "ai", text: nextQ }]);
            }
        } catch (err) {
            setSubmitError(err.message || "Failed to submit. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    }, [sessionId, questionNumber, maxQuestions, token, stopSpeaking, onComplete]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Manual submit (mic button + Space) ──────────────────────────────────
    const handleToggleRecording = useCallback(async () => {
        if (isSubmitting || isRecording) return;
        setSubmitError("");
        try {
            await startRecording();
        } catch (err) {
            const msg = err.name === "NotAllowedError"
                ? "Microphone permission denied. Please allow access and try again."
                : `Could not start recording: ${err.message}`;
            setSubmitError(msg);
        }
    }, [isRecording, isSubmitting, startRecording]);

    const handleSubmitAnswer = useCallback(async () => {
        if (!isRecording || !sessionId || isSubmitting) return;
        try {
            const audioBlob = await stopRecording();
            if (!audioBlob) throw new Error("No audio recorded.");
            await _doSubmit(audioBlob);
        } catch (err) {
            if (!isSubmitting) {
                setSubmitError(err.message || "Failed to submit. Please try again.");
                setIsSubmitting(false);
            }
        }
    }, [isRecording, sessionId, isSubmitting, stopRecording, _doSubmit]);

    // ── VAD speech ended → start 3s submission countdown instead of instant submit
    useEffect(() => {
        if (!vadBlob || isSubmitting || !sessionId || isRecording) return;
        hasSpokeRef.current = true;
        setNoSpeechTimer(null);
        const blob = vadBlob;
        clearBlob();
        setPendingBlob(blob);
        setSilenceCountdown(3);
    }, [vadBlob]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Silence countdown tick → auto-submit at 0 ────────────────────────────
    useEffect(() => {
        if (silenceCountdown === null) return;
        if (silenceCountdown === 0) {
            const blob = pendingBlob;
            setPendingBlob(null);
            setSilenceCountdown(null);
            if (blob && !isSubmitting && sessionId) _doSubmit(blob);
            return;
        }
        const t = setTimeout(() => setSilenceCountdown((c) => c - 1), 1000);
        return () => clearTimeout(t);
    }, [silenceCountdown]); // eslint-disable-line react-hooks/exhaustive-deps

    const cancelCountdown = useCallback(() => {
        setSilenceCountdown(null);
        setPendingBlob(null);
    }, []);

    // ── End early ────────────────────────────────────────────────────────────
    const handleEndInterview = useCallback(async () => {
        if (isEnding) return;
        setIsEnding(true);
        stopSpeaking();
        if (audioRef.current) { audioRef.current.pause(); setIsBackendPlaying(false); }
        if (isRecording) await stopRecording();

        try {
            const evals    = evaluationsRef.current;
            const avgScore = evals.length > 0
                ? evals.reduce((s, e) => s + (e.score || 0), 0) / evals.length
                : 0;
            await completeCandidateInterview(token, sessionId, avgScore, {
                evaluations: evals, summary: "", strengths: [], weaknesses: [],
            }, violationLog);
        } catch { /* non-fatal */ }
        onComplete();
    }, [isEnding, isRecording, sessionId, token, stopSpeaking, stopRecording, onComplete]);

    // ── Space bar shortcut ───────────────────────────────────────────────────
    useEffect(() => {
        const handler = (e) => {
            if (e.code !== "Space" || e.target.tagName === "BUTTON") return;
            e.preventDefault();
            if (isRecording) handleSubmitAnswer();
            else handleToggleRecording();
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [isRecording, handleSubmitAnswer, handleToggleRecording]);

    // ── Derived UI state ─────────────────────────────────────────────────────
    const progressPct = Math.min(((questionNumber - 1) / maxQuestions) * 100, 100);

    const statusLabel = isSubmitting
        ? "Saving and analysing response…"
        : silenceCountdown !== null
        ? `Submitting in ${silenceCountdown}s — keep talking or submit now`
        : preAnswerCountdown !== null
        ? `Answer starts in ${preAnswerCountdown}…`
        : noSpeechTimer !== null && noSpeechTimer <= 20 && !hasSpokeRef.current
        ? `No answer detected — auto-submitting in ${noSpeechTimer}s`
        : isRecording
        ? "Recording — press Submit when done"
        : vadSpeaking
        ? "Speaking detected…"
        : vadListening
        ? "Listening… speak your answer"
        : isMicOn
        ? "Tap the mic to start your answer"
        : "Microphone is muted";

    const statusDot = isSubmitting || silenceCountdown !== null
        ? "bg-warning animate-pulse"
        : preAnswerCountdown !== null
        ? "bg-cobalt animate-pulse"
        : isRecording
        ? "bg-destructive animate-pulse"
        : isMicOn
        ? "bg-mint animate-pulse"
        : "bg-destructive";

    // ── Render ───────────────────────────────────────────────────────────────
    return (
        <div className="h-screen overflow-hidden bg-room flex flex-col">

            {/* Hidden TTS audio element */}
            <audio
                ref={audioRef}
                className="hidden"
                onPlay={() => setIsBackendPlaying(true)}
                onPause={() => setIsBackendPlaying(false)}
                onEnded={() => setIsBackendPlaying(false)}
            />
            {/* Hidden canvas for silent frame capture */}
            <canvas ref={canvasRef} className="hidden" />

            {/* ── TOP BAR ───────────────────────────────────────────────────── */}
            <header className="flex flex-col shrink-0 border-b border-room-border bg-room-surface/50 backdrop-blur-sm">
                <div className="h-1 w-full bg-room-border">
                    <motion.div
                        className="h-full gradient-cobalt"
                        initial={{ width: 0 }}
                        animate={{ width: `${progressPct}%` }}
                        transition={{ duration: 0.5 }}
                    />
                </div>

                <div className="flex items-center justify-between px-6 py-3">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg gradient-cobalt flex items-center justify-center">
                            <Brain className="w-4 h-4 text-primary-foreground" />
                        </div>
                        <span className="text-sm font-bold text-primary-foreground/90">
                            My<span className="text-cobalt-light">HR</span>
                        </span>
                        <span className="hidden sm:inline text-xs text-primary-foreground/40 ml-1">
                            — Live Interview
                        </span>
                    </div>

                    <div className="flex items-center gap-2">
                        {isRecording && (
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-destructive/10 border border-destructive/20">
                                <div className="w-2 h-2 rounded-full bg-destructive animate-pulse" />
                                <span className="text-xs font-medium text-destructive">
                                    REC {fmt(recordingElapsed)}
                                </span>
                            </div>
                        )}
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                            <Clock className="w-3.5 h-3.5 text-cobalt-lighter" />
                            <span className="text-sm font-mono font-medium text-primary-foreground/80">
                                {fmt(elapsed)}
                            </span>
                        </div>
                        <div className="px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                            <span className="text-xs text-muted-foreground">
                                Q{" "}
                                <span className="font-semibold text-primary-foreground">{questionNumber}</span>
                                <span className="text-primary-foreground/40 ml-1">of {maxQuestions}</span>
                            </span>
                        </div>
                    </div>
                </div>
            </header>

            {/* ── SPLIT BODY ────────────────────────────────────────────────── */}
            <div className="flex-1 min-h-0 grid lg:grid-cols-[5fr_7fr] overflow-hidden">

                {/* ══ LEFT: Camera + Controls ══════════════════════════════════ */}
                <div className="flex flex-col p-4 gap-3 border-b lg:border-b-0 lg:border-r border-room-border overflow-hidden bg-room-surface/10">

                    <motion.div
                        initial={{ opacity: 0, scale: 0.96 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.5 }}
                        className="relative flex-1 min-h-0 rounded-xl overflow-hidden"
                    >
                        <div className="absolute inset-0">
                            <CameraFeed
                                videoRef={videoRef}
                                isCameraOn={isCameraOn}
                                error={mediaError}
                                proctorAlert={proctorAlert}
                                warningTier={warningTier}
                                warningMessage={warningMessage}
                                gazeScore={gazeScore}
                                violationCount={violationCount}
                            />
                        </div>
                    </motion.div>

                    <AnimatePresence>
                        {submitError && (
                            <motion.div
                                initial={{ opacity: 0, y: -6 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="flex items-center gap-2 px-3 py-2 rounded-xl bg-destructive/10 border border-destructive/20 shrink-0"
                            >
                                <AlertCircle className="w-4 h-4 text-destructive shrink-0" />
                                <p className="text-xs text-destructive">{submitError}</p>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Controls row */}
                    <div className="flex items-center justify-center gap-3 shrink-0">
                        {/* Camera toggle */}
                        <button
                            onClick={toggleCamera}
                            title={isCameraOn ? "Turn off camera" : "Turn on camera"}
                            className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${
                                isCameraOn
                                    ? "bg-room-surface border border-room-border text-primary-foreground/70 hover:bg-room-border"
                                    : "bg-destructive/15 border border-destructive/30 text-destructive hover:bg-destructive/25"
                            }`}
                        >
                            {isCameraOn ? <Camera className="w-4 h-4" /> : <CameraOff className="w-4 h-4" />}
                        </button>

                        {/* Mic — reflects manual recording OR VAD speech detection */}
                        <button
                            onClick={handleToggleRecording}
                            disabled={isSubmitting || !isMicOn}
                            title={
                                isRecording ? "Recording — press Submit to send"
                                    : vadSpeaking ? "Listening to your answer…"
                                    : "Start recording"
                            }
                            className={`w-14 h-14 rounded-full flex items-center justify-center transition-all disabled:opacity-50 ${
                                isRecording
                                    ? "bg-destructive/20 border-2 border-destructive text-destructive"
                                    : vadSpeaking
                                    ? "bg-destructive/20 border-2 border-destructive text-destructive animate-pulse"
                                    : vadListening
                                    ? "gradient-cobalt shadow-cobalt text-primary-foreground ring-2 ring-mint/50"
                                    : "gradient-cobalt shadow-cobalt text-primary-foreground hover:brightness-110"
                            }`}
                        >
                            {isSubmitting ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : isRecording ? (
                                <div className="w-5 h-5 rounded-sm bg-destructive" />
                            ) : vadSpeaking ? (
                                <Mic className="w-5 h-5 animate-pulse" />
                            ) : (
                                <Mic className="w-5 h-5" />
                            )}
                        </button>

                        {/* Submit (visible while recording) */}
                        <AnimatePresence>
                            {isRecording && (
                                <motion.button
                                    key="submit"
                                    initial={{ opacity: 0, scale: 0.8 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.8 }}
                                    onClick={handleSubmitAnswer}
                                    disabled={isSubmitting}
                                    title="Submit answer (Space)"
                                    className="w-11 h-11 rounded-full flex items-center justify-center bg-mint/20 border border-mint/30 text-mint hover:bg-mint/30 transition-all disabled:opacity-50"
                                >
                                    {isSubmitting ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Send className="w-4 h-4" />
                                    )}
                                </motion.button>
                            )}
                        </AnimatePresence>

                        {/* Mic toggle */}
                        <button
                            onClick={toggleMic}
                            title={isMicOn ? "Mute microphone" : "Unmute microphone"}
                            className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${
                                isMicOn
                                    ? "bg-room-surface border border-room-border text-primary-foreground/70 hover:bg-room-border"
                                    : "bg-destructive/15 border border-destructive/30 text-destructive hover:bg-destructive/25"
                            }`}
                        >
                            {isMicOn ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
                        </button>

                        {/* End interview */}
                        <button
                            onClick={handleEndInterview}
                            disabled={isEnding}
                            title="End interview"
                            className="w-11 h-11 rounded-full flex items-center justify-center bg-destructive/10 border border-destructive/20 text-destructive hover:bg-destructive/20 transition-all disabled:opacity-50"
                        >
                            {isEnding ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <PhoneOff className="w-4 h-4" />
                            )}
                        </button>
                    </div>

                    {/* ── Pre-answer countdown ────────────────────────────── */}
                    <AnimatePresence>
                        {preAnswerCountdown !== null && (
                            <motion.div
                                key="pre-answer"
                                initial={{ opacity: 0, y: 6 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="shrink-0 flex flex-col items-center gap-1 py-2"
                            >
                                <p className="text-xs text-primary-foreground/50">Get ready to answer…</p>
                                <p className="text-5xl font-bold text-cobalt-light">{preAnswerCountdown}</p>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* ── Submission countdown ─────────────────────────────── */}
                    <AnimatePresence>
                        {silenceCountdown !== null && !isSubmitting && (
                            <motion.div
                                key="sub-countdown"
                                initial={{ opacity: 0, y: 6 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="shrink-0 flex items-center gap-3 bg-warning/10 border border-warning/30 rounded-xl px-4 py-2.5"
                            >
                                <p className="text-xs flex-1 text-primary-foreground/70">
                                    Submitting in <span className="font-bold text-warning">{silenceCountdown}s</span>…
                                </p>
                                <Button size="sm" variant="outline" className="text-xs h-7 px-3" onClick={cancelCountdown}>
                                    Keep Talking
                                </Button>
                                <Button size="sm" variant="hero" className="text-xs h-7 px-3" onClick={() => setSilenceCountdown(0)}>
                                    Submit Now
                                </Button>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Status hint */}
                    <div className="flex items-center justify-center gap-2 shrink-0 pb-1">
                        <div className={`w-2 h-2 rounded-full transition-colors ${statusDot}`} />
                        <span className="text-xs text-primary-foreground/50 text-center">
                            {statusLabel}
                        </span>
                    </div>
                </div>

                {/* ══ RIGHT: Question + Waveform + Transcript ══════════════════ */}
                <div className="flex flex-col p-4 gap-3 overflow-hidden">

                    {/* Question player */}
                    <div className="shrink-0">
                        <AnimatePresence mode="wait">
                            <AudioQuestionPlayer
                                key={questionNumber}
                                question={currentQuestion}
                                questionNumber={questionNumber}
                                isPlaying={isPlaying || isBackendPlaying}
                                onTogglePlay={() => {
                                    if (isPlaying || isBackendPlaying) {
                                        stopSpeaking();
                                        if (audioRef.current) audioRef.current.pause();
                                        setIsBackendPlaying(false);
                                    } else {
                                        if (audioUrl && audioRef.current) {
                                            audioRef.current.currentTime = 0;
                                            audioRef.current.play().catch(() => speakQuestion(currentQuestion));
                                        } else {
                                            speakQuestion(currentQuestion);
                                        }
                                    }
                                }}
                                onReplay={() => {
                                    stopSpeaking();
                                    if (audioUrl && audioRef.current) {
                                        audioRef.current.pause();
                                        audioRef.current.currentTime = 0;
                                        audioRef.current.play().catch(() => speakQuestion(currentQuestion));
                                    } else {
                                        speakQuestion(currentQuestion);
                                    }
                                }}
                                audioUrl={audioUrl}
                            />
                        </AnimatePresence>
                    </div>

                    {/* Voice waveform */}
                    <div className="shrink-0">
                        <VoiceWaveform
                            isActive={isMicOn && (isRecording || vadSpeaking)}
                            audioStream={isMicOn ? audioStream : null}
                        />
                    </div>

                    {/* Transcript */}
                    {messages.length > 0 && (
                        <div className="flex-1 min-h-0 flex flex-col rounded-xl bg-room-surface/40 border border-room-border overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-room-border shrink-0">
                                <MessageSquare className="w-3.5 h-3.5 text-cobalt-lighter" />
                                <span className="text-xs font-semibold text-primary-foreground/50">
                                    Transcript
                                </span>
                            </div>
                            <div ref={transcriptRef} className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
                                {messages.map((msg, idx) => (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, y: 4 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.25 }}
                                        className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
                                    >
                                        <div className={`w-5 h-5 rounded-full shrink-0 mt-0.5 flex items-center justify-center text-[9px] font-bold ${
                                            msg.role === "ai"
                                                ? "gradient-cobalt text-primary-foreground"
                                                : "bg-room-border text-primary-foreground/60"
                                        }`}>
                                            {msg.role === "ai" ? "AI" : "U"}
                                        </div>
                                        <div className={`max-w-[85%] px-3 py-2 rounded-xl text-xs leading-relaxed ${
                                            msg.role === "ai"
                                                ? "bg-cobalt/10 text-cobalt-lighter rounded-tl-none"
                                                : "bg-room-surface text-primary-foreground/70 rounded-tr-none"
                                        }`}>
                                            {msg.text}
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// Outer component — handles token validation and phase machine
// Does NOT use any media hooks (no premature permission prompts)
// ─────────────────────────────────────────────────────────────────────────────
const CandidateInterviewPortal = () => {
    const { token } = useParams();

    const [phase,   setPhase]   = useState("loading");
    const [error,   setError]   = useState("");
    const [context, setContext] = useState(null);

    // Passed to EnterpriseInterviewRoom as initial props
    const [sessionId,     setSessionId]     = useState(null);
    const [initQuestion,  setInitQuestion]  = useState("");
    const [initAudioUrl,  setInitAudioUrl]  = useState(null);
    const [initMaxQ,      setInitMaxQ]      = useState(5);

    // Validate token
    useEffect(() => {
        (async () => {
            try {
                const result = await validateInterviewToken(token);
                setContext(result);
                setPhase("welcome");
            } catch (err) {
                setError(err.message || "Invalid interview link.");
                setPhase("error");
            }
        })();
    }, [token]);

    const handleStart = async () => {
        setPhase("loading");
        try {
            const startData = await startInterviewFromToken(token);
            setSessionId(startData.session_id);
            setInitQuestion(startData.question || "Tell me about yourself.");
            setInitAudioUrl(startData.audio_url || null);
            setInitMaxQ(startData.max_questions || 5);
            setPhase("interview");
        } catch (err) {
            setError(err.message || "Failed to start the interview. Please try again.");
            setPhase("error");
        }
    };

    // ── Error ─────────────────────────────────────────────────────────────────
    if (phase === "error") {
        const isExpired = error.includes("expired");
        return (
            <div className="min-h-screen flex items-center justify-center p-6 bg-background">
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                    className="w-full max-w-sm text-center">
                    <div className="bg-card rounded-2xl border border-border p-8 space-y-5 shadow-sm">
                        <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mx-auto">
                            {isExpired
                                ? <Clock className="w-8 h-8 text-warning" />
                                : <AlertCircle className="w-8 h-8 text-destructive" />}
                        </div>
                        <h2 className="text-xl font-bold text-foreground">
                            {isExpired ? "Link Expired" : "Invalid Link"}
                        </h2>
                        <p className="text-sm text-muted-foreground">{error}</p>
                    </div>
                </motion.div>
            </div>
        );
    }

    // ── Loading ───────────────────────────────────────────────────────────────
    if (phase === "loading") {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
            </div>
        );
    }

    // ── Welcome ───────────────────────────────────────────────────────────────
    if (phase === "welcome") {
        return (
            <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,hsl(221_83%_53%/0.06),transparent_55%)]" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,hsl(160_60%_45%/0.05),transparent_55%)]" />

                <motion.div initial={{ opacity: 0, y: 20, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.5 }} className="relative w-full max-w-lg">
                    <div className="bg-card rounded-2xl border border-border p-8 lg:p-10 space-y-6 shadow-cobalt">
                        <div className="text-center space-y-3">
                            <div className="flex items-center justify-center gap-2.5">
                                <div className="w-10 h-10 rounded-xl gradient-cobalt flex items-center justify-center shadow-cobalt">
                                    <Brain className="w-5 h-5 text-primary-foreground" />
                                </div>
                                <span className="text-xl font-bold text-foreground">
                                    My<span className="text-gradient-cobalt">HR</span>
                                </span>
                            </div>
                            <h1 className="text-2xl font-bold text-foreground mt-4">AI Interview</h1>
                            <p className="text-muted-foreground">You've been invited to interview for</p>
                        </div>

                        <div className="bg-muted rounded-xl p-5 space-y-2">
                            <p className="font-semibold text-foreground text-lg">{context?.jobTitle || "Position"}</p>
                            <p className="text-sm text-muted-foreground">at {context?.companyName || "Company"}</p>
                        </div>

                        <div className="space-y-3">
                            <p className="text-sm font-medium text-foreground">What to expect:</p>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                {[
                                    "5–7 questions tailored to the job description",
                                    "Answer using your microphone — camera is optional",
                                    "AI evaluates your responses in real time",
                                    "Results are shared with the hiring team",
                                ].map((item) => (
                                    <li key={item} className="flex items-start gap-2">
                                        <CheckCircle2 className="w-4 h-4 text-mint shrink-0 mt-0.5" />
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <Button variant="hero" className="w-full h-12 text-base" onClick={handleStart}>
                            Begin Interview
                            <ArrowRight className="w-4 h-4 ml-2" />
                        </Button>

                        <p className="text-center text-[11px] text-muted-foreground">
                            Ensure you have a working microphone and a quiet environment.
                        </p>
                    </div>
                </motion.div>
            </div>
        );
    }

    // ── Interview — render inner component (mounts media hooks now) ───────────
    if (phase === "interview") {
        return (
            <EnterpriseInterviewRoom
                token={token}
                sessionId={sessionId}
                initialQuestion={initQuestion}
                initialAudioUrl={initAudioUrl}
                maxQuestionsInit={initMaxQ}
                onComplete={() => setPhase("completed")}
            />
        );
    }

    // ── Completed — NO score, rating, or feedback shown to candidate ──────────
    if (phase === "completed") {
        return (
            <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(160_60%_45%/0.06),transparent_55%)]" />

                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5 }}
                    className="relative w-full max-w-md"
                >
                    <div className="bg-card rounded-2xl border border-border p-10 text-center space-y-6 shadow-sm">
                        <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: "spring", stiffness: 200, damping: 15, delay: 0.2 }}
                        >
                            <div className="w-20 h-20 rounded-full bg-mint/10 flex items-center justify-center mx-auto">
                                <CheckCircle2 className="w-10 h-10 text-mint" />
                            </div>
                        </motion.div>

                        <div className="space-y-2">
                            <h2 className="text-2xl font-bold text-foreground">Interview Complete</h2>
                            <p className="text-muted-foreground leading-relaxed">
                                Thank you for completing the interview. Your responses have been
                                submitted to the hiring team at{" "}
                                <span className="font-medium text-foreground">{context?.companyName}</span>.
                            </p>
                        </div>

                        <div className="bg-muted rounded-xl p-4 text-sm text-muted-foreground">
                            <p>The hiring team will review your performance and may contact you with next steps.</p>
                        </div>

                        <p className="text-xs text-muted-foreground">
                            Powered by My<span className="text-cobalt-light font-medium">HR</span> AI
                        </p>
                    </div>
                </motion.div>
            </div>
        );
    }

    return null;
};

export default CandidateInterviewPortal;
