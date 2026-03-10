import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate, useLocation } from "react-router-dom";
import VoiceWaveform from "@/components/VoiceWaveform";
import CameraFeed from "@/components/CameraFeed";
import AudioQuestionPlayer from "@/components/AudioQuestionPlayer";
import { Button } from "@/components/ui/button";
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
    Square,
} from "lucide-react";

const InterviewRoom = () => {
    const navigate = useNavigate();
    const location = useLocation();

    // Read session data passed from CandidateHome
    const sessionData = location.state;

    // Media devices
    const {
        videoRef,
        stream,
        audioStream,
        isCameraOn,
        isMicOn,
        toggleCamera,
        toggleMic,
        error: mediaError,
    } = useMediaDevices();

    // Audio recorder
    const { isRecording, startRecording, stopRecording } =
        useAudioRecorder(stream);

    // Audio player (TTS fallback)
    const { isPlaying, speakQuestion, stopSpeaking, toggleSpeaking } =
        useAudioPlayer();

    // Interview state
    const [sessionId, setSessionId] = useState(null);
    const [currentQuestion, setCurrentQuestion] = useState("");
    const [audioUrl, setAudioUrl] = useState(null);
    const [questionNumber, setQuestionNumber] = useState(1);
    const [elapsed, setElapsed] = useState(0);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isEnding, setIsEnding] = useState(false);
    const [messages, setMessages] = useState([]);
    const [lastFeedback, setLastFeedback] = useState(null);
    const audioRef = useRef(null);

    // Initialize from route state
    useEffect(() => {
        if (!sessionData) {
            navigate("/candidate");
            return;
        }
        setSessionId(sessionData.session_id);
        setCurrentQuestion(sessionData.question);
        setAudioUrl(sessionData.audio_url || null);
        setMessages([{ role: "ai", text: sessionData.question }]);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Timer
    useEffect(() => {
        const timer = setInterval(() => setElapsed((prev) => prev + 1), 1000);
        return () => clearInterval(timer);
    }, []);

    // Auto-play audio when question changes
    useEffect(() => {
        if (audioUrl && audioRef.current) {
            audioRef.current.src = audioUrl;
            audioRef.current.play().catch(() => {
                // Fallback to browser TTS if audio fails
                if (currentQuestion) speakQuestion(currentQuestion);
            });
        } else if (currentQuestion) {
            // No backend audio → use browser TTS
            const timeout = setTimeout(() => speakQuestion(currentQuestion), 500);
            return () => clearTimeout(timeout);
        }
    }, [audioUrl, currentQuestion]); // eslint-disable-line react-hooks/exhaustive-deps

    const formatTime = (secs) => {
        const m = Math.floor(secs / 60).toString().padStart(2, "0");
        const s = (secs % 60).toString().padStart(2, "0");
        return `${m}:${s}`;
    };

    // Toggle recording
    const handleToggleRecording = useCallback(() => {
        if (isRecording) {
            // Do nothing — user should use the submit button
            return;
        }
        startRecording();
    }, [isRecording, startRecording]);

    // Submit the recorded answer
    const handleSubmitAnswer = useCallback(async () => {
        if (!isRecording || !sessionId) return;

        setIsSubmitting(true);
        stopSpeaking();

        try {
            const audioBlob = await stopRecording();
            if (!audioBlob) {
                setIsSubmitting(false);
                return;
            }

            const resp = await submitAnswer(sessionId, audioBlob);

            // Add user's transcription to messages
            if (resp.transcription) {
                setMessages((prev) => [
                    ...prev,
                    { role: "user", text: resp.transcription },
                ]);
            }

            if (resp.status === "completed") {
                // Interview finished
                setMessages((prev) => [
                    ...prev,
                    { role: "system", text: "Interview completed! Generating report..." },
                ]);
                // Navigate to feedback with report data
                setTimeout(() => {
                    navigate("/feedback", {
                        state: {
                            session_id: sessionId,
                            report: resp.report,
                        },
                    });
                }, 1500);
            } else {
                // Next question
                const nextQ = resp.next_question;
                setCurrentQuestion(nextQ);
                setAudioUrl(resp.audio_url || null);
                setQuestionNumber((prev) => prev + 1);
                setLastFeedback(resp.feedback || null);
                setMessages((prev) => [...prev, { role: "ai", text: nextQ }]);
            }
        } catch (err) {
            console.error("Submit failed:", err);
            setMessages((prev) => [
                ...prev,
                { role: "system", text: `Error: ${err.message}` },
            ]);
        } finally {
            setIsSubmitting(false);
        }
    }, [
        isRecording,
        sessionId,
        stopRecording,
        stopSpeaking,
        navigate,
    ]);

    // End interview early
    const handleEndInterview = useCallback(async () => {
        setIsEnding(true);
        stopSpeaking();
        if (isRecording) await stopRecording();
        navigate("/feedback", {
            state: { session_id: sessionId },
        });
    }, [sessionId, navigate, stopSpeaking, isRecording, stopRecording]);

    // No session data — redirect
    if (!sessionData) {
        return null;
    }

    return (
        <div className="min-h-screen bg-room flex flex-col">
            {/* Hidden audio element for backend TTS */}
            <audio ref={audioRef} className="hidden" />

            {/* ─── Top Bar ─── */}
            <header className="flex items-center justify-between px-6 py-3 border-b border-room-border bg-room-surface/50 backdrop-blur-sm">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg gradient-cobalt flex items-center justify-center">
                        <Brain className="w-4 h-4 text-primary-foreground" />
                    </div>
                    <span className="text-sm font-semibold text-primary-foreground/90">
                        Interv<span className="text-cobalt-light">AI</span>
                    </span>
                    <span className="hidden sm:inline text-xs text-primary-foreground/40 ml-2">
                        — Live Interview
                    </span>
                </div>

                <div className="flex items-center gap-3">
                    {/* Recording indicator */}
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-destructive/10 border border-destructive/20">
                        <div className="w-2 h-2 rounded-full bg-destructive recording-pulse" />
                        <span className="text-xs font-medium text-destructive">REC</span>
                    </div>

                    {/* Timer */}
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                        <Clock className="w-3.5 h-3.5 text-cobalt-lighter" />
                        <span className="text-sm font-mono font-medium text-primary-foreground/80">
                            {formatTime(elapsed)}
                        </span>
                    </div>

                    {/* Question counter */}
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                        <span className="text-xs text-muted-foreground">
                            Q {questionNumber}
                        </span>
                    </div>
                </div>
            </header>

            {/* ─── Main Content ─── */}
            <main className="flex-1 flex flex-col items-center p-4 lg:p-6 relative overflow-hidden">
                {/* Background glows */}
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,hsl(222_64%_33%/0.12),transparent_70%)] pointer-events-none" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,hsl(160_60%_45%/0.05),transparent_60%)] pointer-events-none" />

                {/* ─── Centered Camera Feed ─── */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.6 }}
                    className="relative z-10 w-full max-w-2xl mt-2 mb-4"
                >
                    <div className="aspect-square w-full">
                        <CameraFeed
                            videoRef={videoRef}
                            isCameraOn={isCameraOn}
                            error={mediaError}
                        />
                    </div>
                </motion.div>

                {/* ─── Device Controls ─── */}
                <div className="relative z-10 flex items-center justify-center gap-3 mb-3">
                    {/* Camera toggle */}
                    <button
                        onClick={toggleCamera}
                        className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${isCameraOn
                            ? "bg-room-surface border border-room-border text-primary-foreground/70 hover:bg-room-border"
                            : "bg-destructive/15 border border-destructive/30 text-destructive hover:bg-destructive/25"
                            }`}
                        title={isCameraOn ? "Turn off camera" : "Turn on camera"}
                    >
                        {isCameraOn ? (
                            <Camera className="w-4.5 h-4.5" />
                        ) : (
                            <CameraOff className="w-4.5 h-4.5" />
                        )}
                    </button>

                    {/* Record / Stop toggle */}
                    <button
                        onClick={handleToggleRecording}
                        disabled={isSubmitting || !isMicOn}
                        className={`w-14 h-14 rounded-full flex items-center justify-center transition-all ${isRecording
                            ? "bg-destructive/20 border-2 border-destructive text-destructive animate-pulse hover:bg-destructive/30"
                            : "gradient-cobalt shadow-cobalt glow-cobalt text-primary-foreground hover:brightness-110"
                            } disabled:opacity-50`}
                        title={isRecording ? "Recording..." : "Start recording"}
                    >
                        {isRecording ? (
                            <div className="w-5 h-5 rounded-sm bg-destructive" />
                        ) : (
                            <Mic className="w-5 h-5" />
                        )}
                    </button>

                    {/* Submit Answer */}
                    {isRecording && (
                        <motion.button
                            initial={{ opacity: 0, scale: 0.8 }}
                            animate={{ opacity: 1, scale: 1 }}
                            onClick={handleSubmitAnswer}
                            disabled={isSubmitting}
                            className="w-11 h-11 rounded-full flex items-center justify-center bg-mint/20 border border-mint/30 text-mint hover:bg-mint/30 transition-all disabled:opacity-50"
                            title="Submit answer"
                        >
                            {isSubmitting ? (
                                <Loader2 className="w-4.5 h-4.5 animate-spin" />
                            ) : (
                                <Send className="w-4.5 h-4.5" />
                            )}
                        </motion.button>
                    )}

                    {/* Mic toggle */}
                    <button
                        onClick={toggleMic}
                        className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${isMicOn
                            ? "bg-room-surface border border-room-border text-primary-foreground/70 hover:bg-room-border"
                            : "bg-destructive/15 border border-destructive/30 text-destructive hover:bg-destructive/25"
                            }`}
                        title={isMicOn ? "Mute microphone" : "Unmute microphone"}
                    >
                        {isMicOn ? (
                            <Mic className="w-4 h-4" />
                        ) : (
                            <MicOff className="w-4 h-4" />
                        )}
                    </button>

                    {/* End Interview */}
                    <button
                        onClick={handleEndInterview}
                        disabled={isEnding}
                        className="w-11 h-11 rounded-full flex items-center justify-center bg-destructive/10 border border-destructive/20 text-destructive hover:bg-destructive/20 transition-all disabled:opacity-50"
                        title="End interview"
                    >
                        {isEnding ? (
                            <Loader2 className="w-4.5 h-4.5 animate-spin" />
                        ) : (
                            <PhoneOff className="w-4.5 h-4.5" />
                        )}
                    </button>
                </div>

                {/* Mic & recording status */}
                <div className="relative z-10 flex items-center justify-center gap-2 mb-5">
                    <div
                        className={`w-2 h-2 rounded-full ${isRecording
                            ? "bg-destructive animate-pulse"
                            : isMicOn
                                ? "bg-mint animate-pulse"
                                : "bg-destructive"
                            }`}
                    />
                    <span className="text-xs text-primary-foreground/50">
                        {isRecording
                            ? "Recording your answer..."
                            : isMicOn
                                ? "Microphone active — tap mic to start recording"
                                : "Microphone muted"}
                    </span>
                </div>

                {/* ─── Question + Waveform ─── */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, delay: 0.2 }}
                    className="relative z-10 w-full max-w-2xl flex flex-col items-center"
                >
                    {/* Question Display */}
                    <AnimatePresence mode="wait">
                        <AudioQuestionPlayer
                            key={questionNumber}
                            question={currentQuestion}
                            questionNumber={questionNumber}
                            isPlaying={isPlaying}
                            onTogglePlay={() => toggleSpeaking(currentQuestion)}
                            onReplay={() => speakQuestion(currentQuestion)}
                            audioUrl={audioUrl}
                        />
                    </AnimatePresence>

                    {/* Last feedback */}
                    {lastFeedback && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="mt-4 px-4 py-3 rounded-xl bg-room-surface/60 border border-room-border max-w-xl"
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-semibold text-cobalt-lighter">
                                    Score: {lastFeedback.score}/100
                                </span>
                            </div>
                            <p className="text-xs text-primary-foreground/50">
                                {lastFeedback.feedback}
                            </p>
                        </motion.div>
                    )}

                    {/* Waveform */}
                    <div className="w-full max-w-xl mt-6 mb-6">
                        <VoiceWaveform
                            isActive={isMicOn && isRecording}
                            audioStream={isMicOn ? audioStream : null}
                        />
                    </div>
                </motion.div>

                {/* Chat transcript (collapsible) */}
                {messages.length > 1 && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="relative z-10 w-full max-w-2xl mt-4 max-h-48 overflow-y-auto rounded-xl bg-room-surface/40 border border-room-border p-4 space-y-2"
                    >
                        <p className="text-xs font-semibold text-primary-foreground/40 mb-2">Transcript</p>
                        {messages.map((msg, idx) => (
                            <div
                                key={idx}
                                className={`text-xs leading-relaxed ${msg.role === "ai"
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
