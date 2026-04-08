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
} from "lucide-react";

const TOTAL_QUESTIONS = 5;

const InterviewRoom = () => {
    const navigate  = useNavigate();
    const location  = useLocation();
    const sessionData = location.state;

    // Media devices
    const { videoRef, stream, audioStream, isCameraOn, isMicOn, toggleCamera, toggleMic, error: mediaError } =
        useMediaDevices();

    const { isRecording, startRecording, stopRecording } = useAudioRecorder(stream);
    const { isPlaying, speakQuestion, stopSpeaking, toggleSpeaking } = useAudioPlayer();

    // Interview state
    const [sessionId,      setSessionId]      = useState(null);
    const [currentQuestion, setCurrentQuestion] = useState("");
    const [audioUrl,       setAudioUrl]       = useState(null);
    const [questionNumber, setQuestionNumber] = useState(1);
    const [elapsed,        setElapsed]        = useState(0);
    const [isSubmitting,   setIsSubmitting]   = useState(false);
    const [isEnding,       setIsEnding]       = useState(false);
    const [messages,       setMessages]       = useState([]);
    const [lastFeedback,   setLastFeedback]   = useState(null);
    const [submitError,    setSubmitError]    = useState("");
    
    // Unified Audio & Recording UX States
    const [isBackendPlaying, setIsBackendPlaying] = useState(false);
    const [recordingElapsed, setRecordingElapsed] = useState(0);

    const audioRef = useRef(null);
    // Track whether the user has started recording at least once for this question
    const hasRecordedRef = useRef(false);

    // ── Init from route state ──────────────────────────────────────────────────
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

    // ── Timer ──────────────────────────────────────────────────────────────────
    useEffect(() => {
        const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
        return () => clearInterval(timer);
    }, []);

    // ── Recording Timer ─────────────────────────────────────────────────────────
    useEffect(() => {
        let timer;
        if (isRecording) {
            timer = setInterval(() => setRecordingElapsed((s) => s + 1), 1000);
        } else {
            setRecordingElapsed(0);
        }
        return () => clearInterval(timer);
    }, [isRecording]);

    // ── Auto-play TTS when question changes ───────────────────────────────────
    useEffect(() => {
        hasRecordedRef.current = false; // reset per question
        if (!currentQuestion) return;

        // Force stop any ongoing audio to prevent duplicate overlapping
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

    const formatTime = (secs) => {
        const m = Math.floor(secs / 60).toString().padStart(2, "0");
        const s = (secs % 60).toString().padStart(2, "0");
        return `${m}:${s}`;
    };

    // ── Record / Stop ──────────────────────────────────────────────────────────
    const handleToggleRecording = useCallback(() => {
        if (isSubmitting) return;
        if (isRecording) return; // use Submit button to stop + submit
        setSubmitError("");
        hasRecordedRef.current = true;
        startRecording();
    }, [isRecording, isSubmitting, startRecording]);

    // ── Submit ─────────────────────────────────────────────────────────────────
    const handleSubmitAnswer = useCallback(async () => {
        if (!isRecording || !sessionId || isSubmitting) return;

        setIsSubmitting(true);
        setSubmitError("");
        // Stop any playing audio so it doesn't distract the transition
        stopSpeaking();
        if (audioRef.current) {
            audioRef.current.pause();
            setIsBackendPlaying(false);
        }

        try {
            const audioBlob = await stopRecording();
            if (!audioBlob) throw new Error("No audio recorded.");

            const resp = await submitAnswer(sessionId, audioBlob);

            // Append transcription to chat
            if (resp.transcription) {
                setMessages((prev) => [...prev, { role: "user", text: resp.transcription }]);
            }

            if (resp.status === "completed") {
                setMessages((prev) => [
                    ...prev,
                    { role: "system", text: "Interview complete — generating your report…" },
                ]);
                toast.success("Interview complete!", { description: "Preparing your feedback report…" });

                // Persist report to localStorage for FeedbackReport page
                try {
                    localStorage.setItem(
                        `myhr_report_${sessionId}`,
                        JSON.stringify({ report: resp.report, session_id: sessionId, timestamp: Date.now() })
                    );
                } catch { /* storage full — non-fatal */ }

                setTimeout(() => navigate("/feedback", { state: { session_id: sessionId, report: resp.report } }), 1500);
            } else {
                const nextQ = resp.next_question;
                setCurrentQuestion(nextQ);
                setAudioUrl(resp.audio_url ?? null);
                setQuestionNumber((n) => n + 1);
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

    // ── End early ─────────────────────────────────────────────────────────────
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

    // ── Keyboard shortcut: Space = toggle recording ────────────────────────────
    useEffect(() => {
        const handler = (e) => {
            if (e.code !== "Space" || e.target.tagName === "BUTTON") return;
            e.preventDefault();
            if (isRecording) {
                handleSubmitAnswer();
            } else {
                handleToggleRecording();
            }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [isRecording, handleSubmitAnswer, handleToggleRecording]);

    if (!sessionData) return null;

    const progressPct = ((questionNumber - 1) / TOTAL_QUESTIONS) * 100;

    return (
        <div className="min-h-screen bg-room flex flex-col">
            {/* Hidden audio for backend generated TTS */}
            <audio 
                ref={audioRef} 
                className="hidden" 
                onPlay={() => setIsBackendPlaying(true)}
                onPause={() => setIsBackendPlaying(false)}
                onEnded={() => setIsBackendPlaying(false)}
            />

            {/* ── Top Bar ─────────────────────────────────────────────────────── */}
            <header className="flex flex-col border-b border-room-border bg-room-surface/50 backdrop-blur-sm">
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
                        <span className="text-sm font-semibold text-primary-foreground/90">
                            My<span className="text-cobalt-light">HR</span>
                        </span>
                        <span className="hidden sm:inline text-xs text-primary-foreground/40 ml-2">— Live Interview</span>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Recording dot */}
                        {isRecording && (
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-destructive/10 border border-destructive/20">
                                <div className="w-2 h-2 rounded-full bg-destructive animate-pulse" />
                                <span className="text-xs font-medium text-destructive">REC {formatTime(recordingElapsed)}</span>
                            </div>
                        )}

                        {/* Timer */}
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                            <Clock className="w-3.5 h-3.5 text-cobalt-lighter" />
                            <span className="text-sm font-mono font-medium text-primary-foreground/80">{formatTime(elapsed)}</span>
                        </div>

                        {/* Question counter */}
                        <div className="px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                            <span className="text-xs text-muted-foreground">
                                Q <span className="font-semibold text-primary-foreground">{questionNumber}</span>
                                <span className="text-primary-foreground/40"> / {TOTAL_QUESTIONS}</span>
                            </span>
                        </div>
                    </div>
                </div>
            </header>

            {/* ── Main ─────────────────────────────────────────────────────────── */}
            <main className="flex-1 flex flex-col items-center p-4 lg:p-6 relative overflow-hidden">
                {/* Background glows */}
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,hsl(222_64%_33%/0.12),transparent_70%)] pointer-events-none" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,hsl(160_60%_45%/0.05),transparent_60%)] pointer-events-none" />

                {/* Camera */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5 }}
                    className="relative z-10 w-full max-w-2xl mt-2 mb-4"
                >
                    <div className="aspect-square w-full">
                        <CameraFeed videoRef={videoRef} isCameraOn={isCameraOn} error={mediaError} />
                    </div>
                </motion.div>

                {/* Submit error */}
                <AnimatePresence>
                    {submitError && (
                        <motion.div
                            initial={{ opacity: 0, y: -8 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            className="relative z-10 mb-3 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-destructive/10 border border-destructive/20 max-w-lg w-full"
                        >
                            <AlertCircle className="w-4 h-4 text-destructive shrink-0" />
                            <p className="text-sm text-destructive">{submitError}</p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Controls */}
                <div className="relative z-10 flex items-center justify-center gap-3 mb-2">
                    {/* Camera toggle */}
                    <button
                        onClick={toggleCamera}
                        className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${
                            isCameraOn
                                ? "bg-room-surface border border-room-border text-primary-foreground/70 hover:bg-room-border"
                                : "bg-destructive/15 border border-destructive/30 text-destructive hover:bg-destructive/25"
                        }`}
                        title={isCameraOn ? "Turn off camera" : "Turn on camera"}
                    >
                        {isCameraOn ? <Camera className="w-4 h-4" /> : <CameraOff className="w-4 h-4" />}
                    </button>

                    {/* Record button */}
                    <button
                        onClick={handleToggleRecording}
                        disabled={isSubmitting || !isMicOn}
                        className={`w-14 h-14 rounded-full flex items-center justify-center transition-all disabled:opacity-50 ${
                            isRecording
                                ? "bg-destructive/20 border-2 border-destructive text-destructive"
                                : "gradient-cobalt shadow-cobalt text-primary-foreground hover:brightness-110"
                        }`}
                        title={isRecording ? "Recording — press Submit to send" : "Start recording"}
                    >
                        {isSubmitting ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : isRecording ? (
                            <div className="w-5 h-5 rounded-sm bg-destructive" />
                        ) : (
                            <Mic className="w-5 h-5" />
                        )}
                    </button>

                    {/* Submit — visible while recording */}
                    <AnimatePresence>
                        {isRecording && (
                            <motion.button
                                key="submit"
                                initial={{ opacity: 0, scale: 0.8 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.8 }}
                                onClick={handleSubmitAnswer}
                                disabled={isSubmitting}
                                className="w-11 h-11 rounded-full flex items-center justify-center bg-mint/20 border border-mint/30 text-mint hover:bg-mint/30 transition-all disabled:opacity-50"
                                title="Submit answer (Space)"
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
                        className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${
                            isMicOn
                                ? "bg-room-surface border border-room-border text-primary-foreground/70 hover:bg-room-border"
                                : "bg-destructive/15 border border-destructive/30 text-destructive hover:bg-destructive/25"
                        }`}
                        title={isMicOn ? "Mute microphone" : "Unmute microphone"}
                    >
                        {isMicOn ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
                    </button>

                    {/* End interview */}
                    <button
                        onClick={handleEndInterview}
                        disabled={isEnding}
                        className="w-11 h-11 rounded-full flex items-center justify-center bg-destructive/10 border border-destructive/20 text-destructive hover:bg-destructive/20 transition-all disabled:opacity-50"
                        title="End interview"
                    >
                        {isEnding ? <Loader2 className="w-4 h-4 animate-spin" /> : <PhoneOff className="w-4 h-4" />}
                    </button>
                </div>

                {/* Status hint */}
                <div className="relative z-10 flex items-center justify-center gap-2 mb-5">
                    <div
                        className={`w-2 h-2 rounded-full transition-colors ${
                            isRecording ? "bg-destructive animate-pulse" : isMicOn ? "bg-mint animate-pulse" : "bg-destructive"
                        }`}
                    />
                    <span className="text-xs text-primary-foreground/50">
                        {isSubmitting
                            ? "Saving and analyzing response..."
                            : isRecording
                            ? "Recording in progress... press Submit when finished"
                            : isMicOn
                            ? "Tap the mic button to start your response"
                            : "Microphone is muted"}
                    </span>
                </div>

                {/* Question + waveform */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="relative z-10 w-full max-w-2xl flex flex-col items-center"
                >
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

                    {/* Last feedback badge */}
                    <AnimatePresence>
                        {lastFeedback && (
                            <motion.div
                                key="feedback"
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="mt-4 px-4 py-3 rounded-xl bg-room-surface/60 border border-room-border max-w-xl w-full"
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
                                    <span className="text-xs text-primary-foreground/40">Previous answer</span>
                                </div>
                                <p className="text-xs text-primary-foreground/50 leading-relaxed">{lastFeedback.feedback}</p>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Waveform */}
                    <div className="w-full max-w-xl mt-6 mb-6">
                        <VoiceWaveform isActive={isMicOn && isRecording} audioStream={isMicOn ? audioStream : null} />
                    </div>
                </motion.div>

                {/* Transcript (collapsible, appears after first exchange) */}
                {messages.length > 1 && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="relative z-10 w-full max-w-2xl mt-4 max-h-48 overflow-y-auto rounded-xl bg-room-surface/40 border border-room-border p-4 space-y-2"
                    >
                        <p className="text-xs font-semibold text-primary-foreground/40 mb-2 sticky top-0">Transcript</p>
                        {messages.map((msg, idx) => (
                            <div
                                key={idx}
                                className={`text-xs leading-relaxed ${
                                    msg.role === "ai"
                                        ? "text-cobalt-lighter"
                                        : msg.role === "user"
                                        ? "text-primary-foreground/70"
                                        : "text-warning"
                                }`}
                            >
                                <span className="font-semibold">
                                    {msg.role === "ai" ? "AI: " : msg.role === "user" ? "You: " : ""}
                                </span>
                                {msg.text}
                            </div>
                        ))}
                    </motion.div>
                )}
            </main>
        </div>
    );
};

export default InterviewRoom;
