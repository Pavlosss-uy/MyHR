import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import VoiceWaveform from "@/components/VoiceWaveform";
import CameraFeed from "@/components/CameraFeed";
import AudioQuestionPlayer from "@/components/AudioQuestionPlayer";
import { useMediaDevices } from "@/hooks/useMediaDevices";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { submitAnswer } from "@/lib/interviewApi";
import {
    Mic,
    MicOff,
    Camera,
    CameraOff,
    PhoneOff,
    Brain,
    Clock,
    Loader2,
    Send,
    AlertCircle,
    MessageSquare,
} from "lucide-react";

// Max is returned by the backend per-session (adaptive).
// We keep a local fallback only for the progress bar initial render.
const FALLBACK_MAX_QUESTIONS = 7;

const InterviewRoom = () => {
    const navigate   = useNavigate();
    const location   = useLocation();
    const sessionData = location.state;

    // Media devices
    const {
        videoRef, stream, audioStream,
        isCameraOn, isMicOn,
        toggleCamera, toggleMic,
        error: mediaError,
    } = useMediaDevices();

    const { isRecording, startRecording, stopRecording } = useAudioRecorder(stream);
    const { isPlaying, speakQuestion, stopSpeaking }     = useAudioPlayer();

    // Interview state
    const [sessionId,       setSessionId]       = useState(null);
    const [currentQuestion, setCurrentQuestion] = useState("");
    const [audioUrl,        setAudioUrl]        = useState(null);
    const [questionNumber,  setQuestionNumber]  = useState(1);
    const [elapsed,         setElapsed]         = useState(0);
    const [isSubmitting,    setIsSubmitting]    = useState(false);
    const [isEnding,        setIsEnding]        = useState(false);
    const [messages,        setMessages]        = useState([]);
    const [lastFeedback,    setLastFeedback]    = useState(null);
    const [submitError,     setSubmitError]     = useState("");
    const [maxQuestions,    setMaxQuestions]    = useState(FALLBACK_MAX_QUESTIONS);

    const [isBackendPlaying, setIsBackendPlaying] = useState(false);
    const [recordingElapsed, setRecordingElapsed] = useState(0);
    const [showTranscript,   setShowTranscript]   = useState(false);

    const audioRef       = useRef(null);
    const transcriptRef  = useRef(null);
    const hasRecordedRef = useRef(false);

    // ── Init ──────────────────────────────────────────────────────────────────
    useEffect(() => {
        if (!sessionData) {
            navigate("/candidate", { replace: true });
            return;
        }
        setSessionId(sessionData.session_id);
        setCurrentQuestion(sessionData.question);
        setAudioUrl(sessionData.audio_url ?? null);
        setMessages([{ role: "ai", text: sessionData.question }]);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Timers ─────────────────────────────────────────────────────────────
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

    // ── Auto-scroll transcript ─────────────────────────────────────────────
    useEffect(() => {
        if (transcriptRef.current) {
            transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
        }
    }, [messages]);

    // ── Auto-play TTS when question changes ─────────────────────────────────
    useEffect(() => {
        hasRecordedRef.current = false;
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

    const fmt = (secs) => {
        const m = Math.floor(secs / 60).toString().padStart(2, "0");
        const s = (secs % 60).toString().padStart(2, "0");
        return `${m}:${s}`;
    };

    // ── Record ─────────────────────────────────────────────────────────────
    const handleToggleRecording = useCallback(async () => {
        if (isSubmitting) return;
        if (isRecording) return;
        setSubmitError("");
        hasRecordedRef.current = true;
        try {
            await startRecording();
        } catch (err) {
            const msg =
                err.name === "NotAllowedError"
                    ? "Microphone permission denied. Please allow access and try again."
                    : `Could not start recording: ${err.message}`;
            setSubmitError(msg);
            toast.error("Microphone required", { description: msg });
        }
    }, [isRecording, isSubmitting, startRecording]);

    // ── Submit ─────────────────────────────────────────────────────────────
    const handleSubmitAnswer = useCallback(async () => {
        if (!isRecording || !sessionId || isSubmitting) return;

        setIsSubmitting(true);
        setSubmitError("");
        stopSpeaking();
        if (audioRef.current) {
            audioRef.current.pause();
            setIsBackendPlaying(false);
        }

        try {
            const audioBlob = await stopRecording();
            if (!audioBlob) throw new Error("No audio recorded.");

            const resp = await submitAnswer(sessionId, audioBlob);

            if (resp.transcription) {
                setMessages((prev) => [...prev, { role: "user", text: resp.transcription }]);
            }

            if (resp.status === "completed") {
                setMessages((prev) => [
                    ...prev,
                    { role: "system", text: "Interview complete — generating your report…" },
                ]);
                toast.success("Interview complete!", { description: "Preparing your feedback report…" });

                try {
                    localStorage.setItem(
                        `myhr_report_${sessionId}`,
                        JSON.stringify({ report: resp.report, session_id: sessionId, timestamp: Date.now() })
                    );
                } catch { /* storage full — non-fatal */ }

                setTimeout(
                    () => navigate("/feedback", { state: { session_id: sessionId, report: resp.report } }),
                    1500
                );
            } else {
                const nextQ = resp.next_question;
                setCurrentQuestion(nextQ);
                setAudioUrl(resp.audio_url ?? null);
                // Use backend-reported number when available; fall back to local increment
                if (resp.question_number != null) {
                    setQuestionNumber(resp.question_number);
                } else {
                    setQuestionNumber((n) => n + 1);
                }
                if (resp.max_questions != null) setMaxQuestions(resp.max_questions);
                setLastFeedback(resp.feedback ?? null);
                setMessages((prev) => [...prev, { role: "ai", text: nextQ }]);
            }
        } catch (err) {
            const msg = err.message || "Failed to submit. Please try again.";
            setSubmitError(msg);
            toast.error("Submission failed", { description: msg });
        } finally {
            setIsSubmitting(false);
        }
    }, [isRecording, sessionId, isSubmitting, stopRecording, stopSpeaking, navigate]);

    // ── End early ──────────────────────────────────────────────────────────
    const handleEndInterview = useCallback(async () => {
        if (isEnding) return;
        setIsEnding(true);
        stopSpeaking();
        if (audioRef.current) {
            audioRef.current.pause();
            setIsBackendPlaying(false);
        }
        if (isRecording) await stopRecording();
        navigate("/feedback", { state: { session_id: sessionId } });
    }, [sessionId, navigate, stopSpeaking, isRecording, stopRecording, isEnding]);

    // ── Space shortcut ─────────────────────────────────────────────────────
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

    if (!sessionData) return null;

    const progressPct = Math.min(((questionNumber - 1) / maxQuestions) * 100, 100);

    /* ─── Status label ───────────────────────────────────────────────────── */
    const statusLabel = isSubmitting
        ? "Saving and analysing response…"
        : isRecording
        ? "Recording… press Submit when done"
        : isMicOn
        ? "Tap the mic to start your answer"
        : "Microphone is muted";

    const statusDot = isRecording
        ? "bg-destructive animate-pulse"
        : isMicOn
        ? "bg-mint animate-pulse"
        : "bg-destructive";

    /* ═════════════════════════════════════════════════════════════════════ */
    return (
        /* Root: locked to viewport — no page scroll */
        <div className="h-screen overflow-hidden bg-room flex flex-col">

            {/* Hidden TTS audio element */}
            <audio
                ref={audioRef}
                className="hidden"
                onPlay={() => setIsBackendPlaying(true)}
                onPause={() => setIsBackendPlaying(false)}
                onEnded={() => setIsBackendPlaying(false)}
            />

            {/* ── TOP BAR ─────────────────────────────────────────────────── */}
            <header className="flex flex-col shrink-0 border-b border-room-border bg-room-surface/50 backdrop-blur-sm">
                {/* Progress bar */}
                <div className="h-1 w-full bg-room-border">
                    <motion.div
                        className="h-full gradient-cobalt"
                        initial={{ width: 0 }}
                        animate={{ width: `${progressPct}%` }}
                        transition={{ duration: 0.5 }}
                    />
                </div>

                <div className="flex items-center justify-between px-6 py-3">
                    {/* Brand */}
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
                        {/* Recording indicator */}
                        {isRecording && (
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-destructive/10 border border-destructive/20">
                                <div className="w-2 h-2 rounded-full bg-destructive animate-pulse" />
                                <span className="text-xs font-medium text-destructive">
                                    REC {fmt(recordingElapsed)}
                                </span>
                            </div>
                        )}

                        {/* Timer */}
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                            <Clock className="w-3.5 h-3.5 text-cobalt-lighter" />
                            <span className="text-sm font-mono font-medium text-primary-foreground/80">
                                {fmt(elapsed)}
                            </span>
                        </div>

                        {/* Question counter — adaptive, no fixed total shown */}
                        <div className="px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                            <span className="text-xs text-muted-foreground">
                                Q{" "}
                                <span className="font-semibold text-primary-foreground">
                                    {questionNumber}
                                </span>
                                <span className="text-primary-foreground/40 ml-1">adaptive</span>
                            </span>
                        </div>
                    </div>
                </div>
            </header>

            {/* ── SPLIT BODY ──────────────────────────────────────────────── */}
            {/*
                Desktop (lg+): two-column grid
                  LEFT  (5 parts) — camera + media controls
                  RIGHT (7 parts) — question + feedback + transcript
                Mobile: single column, camera then question
            */}
            <div className="flex-1 min-h-0 grid lg:grid-cols-[5fr_7fr] overflow-hidden">

                {/* ══ LEFT PANEL: Camera + Controls ═════════════════════════ */}
                <div className="flex flex-col p-4 gap-3 border-b lg:border-b-0 lg:border-r border-room-border overflow-hidden bg-room-surface/10">

                    {/* Camera — grows to fill available vertical space */}
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
                            />
                        </div>
                    </motion.div>

                    {/* Submit error */}
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

                        {/* Record */}
                        <button
                            onClick={handleToggleRecording}
                            disabled={isSubmitting || !isMicOn}
                            title={isRecording ? "Recording — press Submit to send" : "Start recording"}
                            className={`w-14 h-14 rounded-full flex items-center justify-center transition-all disabled:opacity-50 ${
                                isRecording
                                    ? "bg-destructive/20 border-2 border-destructive text-destructive"
                                    : "gradient-cobalt shadow-cobalt text-primary-foreground hover:brightness-110"
                            }`}
                        >
                            {isSubmitting ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : isRecording ? (
                                <div className="w-5 h-5 rounded-sm bg-destructive" />
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

                    {/* Status hint */}
                    <div className="flex items-center justify-center gap-2 shrink-0 pb-1">
                        <div className={`w-2 h-2 rounded-full transition-colors ${statusDot}`} />
                        <span className="text-xs text-primary-foreground/50 text-center">
                            {statusLabel}
                        </span>
                    </div>
                </div>

                {/* ══ RIGHT PANEL: Question + Waveform + Feedback + Transcript ═ */}
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
                                            audioRef.current
                                                .play()
                                                .catch(() => speakQuestion(currentQuestion));
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
                                        audioRef.current
                                            .play()
                                            .catch(() => speakQuestion(currentQuestion));
                                    } else {
                                        speakQuestion(currentQuestion);
                                    }
                                }}
                                audioUrl={audioUrl}
                            />
                        </AnimatePresence>
                    </div>

                    {/* Waveform */}
                    <div className="shrink-0">
                        <VoiceWaveform
                            isActive={isMicOn && isRecording}
                            audioStream={isMicOn ? audioStream : null}
                        />
                    </div>

                    {/* Last feedback badge */}
                    <AnimatePresence>
                        {lastFeedback && (
                            <motion.div
                                key="feedback"
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="shrink-0 px-4 py-3 rounded-xl bg-room-surface/60 border border-room-border"
                            >
                                <div className="flex items-center gap-2 mb-1">
                                    <span
                                        className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                                            lastFeedback.score >= 80
                                                ? "bg-mint/20 text-mint"
                                                : lastFeedback.score >= 60
                                                ? "bg-cobalt/20 text-cobalt-lighter"
                                                : "bg-warning/20 text-warning"
                                        }`}
                                    >
                                        {lastFeedback.score}/100
                                    </span>
                                    <span className="text-xs text-primary-foreground/40">
                                        Previous answer
                                    </span>
                                </div>
                                <p className="text-xs text-primary-foreground/50 leading-relaxed">
                                    {lastFeedback.feedback}
                                </p>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Transcript — scrollable, fills remaining space */}
                    {messages.length > 0 && (
                        <div className="flex-1 min-h-0 flex flex-col rounded-xl bg-room-surface/40 border border-room-border overflow-hidden">
                            {/* Transcript header */}
                            <div className="flex items-center justify-between px-4 py-2.5 border-b border-room-border shrink-0">
                                <div className="flex items-center gap-2">
                                    <MessageSquare className="w-3.5 h-3.5 text-cobalt-lighter" />
                                    <span className="text-xs font-semibold text-primary-foreground/50">
                                        Transcript
                                    </span>
                                </div>
                                <button
                                    onClick={() => setShowTranscript((v) => !v)}
                                    className="text-xs text-primary-foreground/30 hover:text-primary-foreground/60 transition-colors"
                                >
                                    {showTranscript ? "Collapse" : "Expand"}
                                </button>
                            </div>

                            {/* Messages */}
                            <div
                                ref={transcriptRef}
                                className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3"
                            >
                                {messages.map((msg, idx) => (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, y: 4 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.25 }}
                                        className={`flex gap-2 ${
                                            msg.role === "user" ? "flex-row-reverse" : ""
                                        }`}
                                    >
                                        {/* Avatar dot */}
                                        <div
                                            className={`w-5 h-5 rounded-full shrink-0 mt-0.5 flex items-center justify-center text-[9px] font-bold ${
                                                msg.role === "ai"
                                                    ? "gradient-cobalt text-primary-foreground"
                                                    : msg.role === "system"
                                                    ? "bg-warning/30 text-warning"
                                                    : "bg-room-border text-primary-foreground/60"
                                            }`}
                                        >
                                            {msg.role === "ai" ? "AI" : msg.role === "user" ? "U" : "!"}
                                        </div>

                                        {/* Bubble */}
                                        <div
                                            className={`max-w-[85%] px-3 py-2 rounded-xl text-xs leading-relaxed ${
                                                msg.role === "ai"
                                                    ? "bg-cobalt/10 text-cobalt-lighter rounded-tl-none"
                                                    : msg.role === "system"
                                                    ? "bg-warning/10 text-warning rounded-tl-none"
                                                    : "bg-room-surface text-primary-foreground/70 rounded-tr-none"
                                            }`}
                                        >
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

export default InterviewRoom;
