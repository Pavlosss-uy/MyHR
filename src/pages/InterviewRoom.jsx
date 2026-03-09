import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import VoiceWaveform from "@/components/VoiceWaveform";
import CameraFeed from "@/components/CameraFeed";
import AudioQuestionPlayer from "@/components/AudioQuestionPlayer";
import { Button } from "@/components/ui/button";
import { useMediaDevices } from "@/hooks/useMediaDevices";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import {
    fetchInterviewQuestions,
    fetchInterviewSession,
    submitAnswer,
    endInterviewSession,
} from "@/lib/mockInterviewApi";
import {
    Mic,
    MicOff,
    Camera,
    CameraOff,
    PhoneOff,
    Brain,
    Clock,
    ChevronRight,
    ChevronLeft,
    Loader2,
    MessageSquareText,
} from "lucide-react";

const InterviewRoom = () => {
    const navigate = useNavigate();

    // Media devices
    const {
        videoRef,
        audioStream,
        isCameraOn,
        isMicOn,
        toggleCamera,
        toggleMic,
        error: mediaError,
    } = useMediaDevices();

    // Audio player (TTS)
    const { isPlaying, speakQuestion, stopSpeaking, toggleSpeaking } =
        useAudioPlayer();

    // Interview state
    const [questions, setQuestions] = useState([]);
    const [session, setSession] = useState(null);
    const [currentQuestion, setCurrentQuestion] = useState(0);
    const [elapsed, setElapsed] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isEnding, setIsEnding] = useState(false);

    // Live transcript state (speech recognition)
    const [transcript, setTranscript] = useState("");
    const [interimTranscript, setInterimTranscript] = useState("");
    const recognitionRef = useRef(null);
    const isPlayingRef = useRef(false); // mirror of isPlaying for use inside callbacks

    // Keep isPlayingRef in sync so the onresult callback can read it
    useEffect(() => {
        isPlayingRef.current = isPlaying;
    }, [isPlaying]);

    // Speech recognition setup
    useEffect(() => {
        const SpeechRecognition =
            window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) return;

        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";

        recognition.onresult = (event) => {
            // Ignore any results while TTS is playing (avoid transcribing speaker audio)
            if (isPlayingRef.current) return;

            let interim = "";
            let final = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const t = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    final += t + " ";
                } else {
                    interim += t;
                }
            }
            if (final) {
                setTranscript((prev) => (prev + " " + final).trim());
            }
            setInterimTranscript(interim);
        };

        recognition.onerror = () => { };

        recognition.onend = () => {
            // Auto-restart if ref is still set (mic is on)
            if (recognitionRef.current) {
                try { recognition.start(); } catch { }
            }
        };

        recognitionRef.current = recognition;

        return () => {
            recognitionRef.current = null;
            try { recognition.stop(); } catch { }
        };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Start/stop recognition when mic toggles
    useEffect(() => {
        if (!recognitionRef.current) return;
        if (isMicOn) {
            try { recognitionRef.current.start(); } catch { }
        } else {
            try { recognitionRef.current.stop(); } catch { }
            setInterimTranscript("");
        }
    }, [isMicOn]);

    // Reset transcript on question change
    useEffect(() => {
        setTranscript("");
        setInterimTranscript("");
    }, [currentQuestion]);

    // Load interview data from mock API
    useEffect(() => {
        async function loadInterview() {
            try {
                const [questionsRes, sessionRes] = await Promise.all([
                    fetchInterviewQuestions(),
                    fetchInterviewSession(),
                ]);
                if (questionsRes.success) setQuestions(questionsRes.data);
                if (sessionRes.success) setSession(sessionRes.data);
            } catch (err) {
                console.error("Failed to load interview:", err);
            } finally {
                setIsLoading(false);
            }
        }
        loadInterview();
    }, []);

    // Timer
    useEffect(() => {
        const timer = setInterval(() => setElapsed((prev) => prev + 1), 1000);
        return () => clearInterval(timer);
    }, []);

    // Auto-speak question when it changes
    useEffect(() => {
        if (questions.length > 0 && !isLoading) {
            const timeout = setTimeout(() => {
                speakQuestion(questions[currentQuestion].text);
            }, 800);
            return () => clearTimeout(timeout);
        }
    }, [currentQuestion, questions, isLoading]); // eslint-disable-line react-hooks/exhaustive-deps

    const formatTime = (secs) => {
        const m = Math.floor(secs / 60).toString().padStart(2, "0");
        const s = (secs % 60).toString().padStart(2, "0");
        return `${m}:${s}`;
    };

    const handleNextQuestion = useCallback(async () => {
        if (currentQuestion >= questions.length - 1) return;
        setIsSubmitting(true);
        stopSpeaking();
        try {
            await submitAnswer(questions[currentQuestion].id, null);
        } catch (err) {
            console.error("Submit failed:", err);
        }
        setIsSubmitting(false);
        setCurrentQuestion((prev) => prev + 1);
    }, [currentQuestion, questions, stopSpeaking]);

    const handlePrevQuestion = useCallback(() => {
        if (currentQuestion <= 0) return;
        stopSpeaking();
        setCurrentQuestion((prev) => prev - 1);
    }, [currentQuestion, stopSpeaking]);

    const handleEndInterview = useCallback(async () => {
        setIsEnding(true);
        stopSpeaking();
        try {
            await endInterviewSession();
        } catch (err) {
            console.error("End session failed:", err);
        }
        navigate("/feedback");
    }, [navigate, stopSpeaking]);

    // Loading state
    if (isLoading) {
        return (
            <div className="min-h-screen bg-room flex items-center justify-center">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex flex-col items-center gap-4"
                >
                    <Loader2 className="w-8 h-8 text-cobalt-lighter animate-spin" />
                    <p className="text-sm text-primary-foreground/60">
                        Preparing your interview...
                    </p>
                </motion.div>
            </div>
        );
    }

    const currentQ = questions[currentQuestion] || null;
    const displayTranscript = (transcript + " " + interimTranscript).trim();

    return (
        <div className="h-screen bg-room flex flex-col overflow-hidden">
            {/* ─── Top Bar ─── */}
            <header className="flex items-center justify-between px-4 lg:px-6 py-2.5 border-b border-room-border bg-room-surface/50 backdrop-blur-sm shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg gradient-cobalt flex items-center justify-center">
                        <Brain className="w-4 h-4 text-primary-foreground" />
                    </div>
                    <span className="text-sm font-semibold text-primary-foreground/90">
                        Interv<span className="text-cobalt-light">AI</span>
                    </span>
                    {session && (
                        <span className="hidden sm:inline text-xs text-primary-foreground/40 ml-2">
                            — {session.jobTitle}
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2 lg:gap-3">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-destructive/10 border border-destructive/20">
                        <div className="w-2 h-2 rounded-full bg-destructive recording-pulse" />
                        <span className="text-xs font-medium text-destructive">REC</span>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                        <Clock className="w-3.5 h-3.5 text-cobalt-lighter" />
                        <span className="text-sm font-mono font-medium text-primary-foreground/80">
                            {formatTime(elapsed)}
                        </span>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-room-surface border border-room-border">
                        <span className="text-xs text-muted-foreground">
                            Q {currentQuestion + 1}/{questions.length}
                        </span>
                    </div>
                </div>
            </header>

            {/* ─── Main Content — Single Unified Panel ─── */}
            <main className="flex-1 flex flex-col lg:flex-row gap-3 p-3 lg:p-4 min-h-0 relative overflow-hidden">
                {/* Background glows */}
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,hsl(222_64%_33%/0.12),transparent_70%)] pointer-events-none" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,hsl(160_60%_45%/0.05),transparent_60%)] pointer-events-none" />

                {/* ── LEFT: Camera Feed ── */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.6 }}
                    className="relative z-10 lg:w-[45%] flex-shrink-0 rounded-2xl overflow-hidden border border-room-border bg-room-surface"
                >
                    <div className="h-full w-full min-h-[240px] lg:min-h-0">
                        <CameraFeed
                            videoRef={videoRef}
                            isCameraOn={isCameraOn}
                            error={mediaError}
                        />
                    </div>

                    {/* Camera status overlay at bottom */}
                    <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                            <div className={`w-2 h-2 rounded-full ${isMicOn ? "bg-mint animate-pulse" : "bg-destructive"}`} />
                            <span className="text-[10px] text-white/60 font-medium">
                                {isMicOn ? "MIC ON" : "MIC OFF"}
                            </span>
                        </div>
                    </div>
                </motion.div>

                {/* ── RIGHT: Question + Waveform + Controls ── */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, delay: 0.15 }}
                    className="relative z-10 flex-1 flex flex-col min-h-0 rounded-2xl border border-room-border bg-room-surface/60 backdrop-blur-sm overflow-hidden"
                >
                    {/* Question area */}
                    <div className="flex-1 flex flex-col items-center justify-center px-4 lg:px-8 py-4 min-h-0 overflow-y-auto">
                        <AnimatePresence mode="wait">
                            <AudioQuestionPlayer
                                key={currentQ?.id}
                                question={currentQ}
                                questionIndex={currentQuestion}
                                totalQuestions={questions.length}
                                isPlaying={isPlaying}
                                onTogglePlay={() => toggleSpeaking(currentQ?.text)}
                                onReplay={() => speakQuestion(currentQ?.text)}
                            />
                        </AnimatePresence>

                        {/* Waveform */}
                        <div className="w-full max-w-md mt-4 mb-2">
                            <VoiceWaveform
                                isActive={isMicOn}
                                audioStream={isMicOn ? audioStream : null}
                            />
                        </div>

                        {/* Question Navigation */}
                        <div className="flex items-center gap-3 mt-2">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handlePrevQuestion}
                                disabled={currentQuestion === 0}
                                className="gap-1.5 text-primary-foreground/50 hover:text-primary-foreground/80 disabled:opacity-30"
                            >
                                <ChevronLeft className="w-4 h-4" />
                                Previous
                            </Button>

                            <div className="flex items-center gap-1.5 px-3">
                                {questions.map((_, idx) => (
                                    <div
                                        key={idx}
                                        className={`w-2 h-2 rounded-full transition-all ${idx === currentQuestion
                                            ? "bg-cobalt-light scale-125"
                                            : idx < currentQuestion
                                                ? "bg-mint/60"
                                                : "bg-room-border"
                                            }`}
                                    />
                                ))}
                            </div>

                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleNextQuestion}
                                disabled={currentQuestion >= questions.length - 1 || isSubmitting}
                                className="gap-1.5 text-cobalt-lighter hover:text-cobalt-light disabled:opacity-30"
                            >
                                {isSubmitting ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Submitting...
                                    </>
                                ) : (
                                    <>
                                        Next
                                        <ChevronRight className="w-4 h-4" />
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>

                    {/* ─── Transcript Bar ─── */}
                    <div className="shrink-0 border-t border-room-border bg-room-surface/80 px-4 py-3">
                        <div className="flex items-start gap-2">
                            <MessageSquareText className="w-4 h-4 text-cobalt-lighter mt-0.5 shrink-0" />
                            <div className="flex-1 min-h-[20px] max-h-[60px] overflow-y-auto">
                                {displayTranscript ? (
                                    <p className="text-sm text-primary-foreground/80 leading-relaxed">
                                        {transcript}
                                        {interimTranscript && (
                                            <span className="text-primary-foreground/40 italic">
                                                {" "}{interimTranscript}
                                            </span>
                                        )}
                                    </p>
                                ) : (
                                    <p className="text-xs text-primary-foreground/30 italic">
                                        {isMicOn
                                            ? "Listening... speak and your words will appear here"
                                            : "Microphone is muted — unmute to see live transcript"}
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>
                </motion.div>
            </main>

            {/* ─── Bottom Control Bar ─── */}
            <footer className="shrink-0 flex items-center justify-center gap-3 px-4 py-3 border-t border-room-border bg-room-surface/50 backdrop-blur-sm">
                {/* Camera toggle */}
                <button
                    onClick={toggleCamera}
                    className={`w-11 h-11 rounded-full flex items-center justify-center transition-all ${isCameraOn
                        ? "bg-room-surface border border-room-border text-primary-foreground/70 hover:bg-room-border"
                        : "bg-destructive/15 border border-destructive/30 text-destructive hover:bg-destructive/25"
                        }`}
                    title={isCameraOn ? "Turn off camera" : "Turn on camera"}
                >
                    {isCameraOn ? <Camera className="w-4.5 h-4.5" /> : <CameraOff className="w-4.5 h-4.5" />}
                </button>

                {/* Mic toggle */}
                <button
                    onClick={toggleMic}
                    className={`w-14 h-14 rounded-full flex items-center justify-center transition-all ${isMicOn
                        ? "gradient-cobalt shadow-cobalt glow-cobalt text-primary-foreground hover:brightness-110"
                        : "bg-destructive/15 border-2 border-destructive text-destructive hover:bg-destructive/25"
                        }`}
                    title={isMicOn ? "Mute microphone" : "Unmute microphone"}
                >
                    {isMicOn ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
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
            </footer>
        </div>
    );
};

export default InterviewRoom;
