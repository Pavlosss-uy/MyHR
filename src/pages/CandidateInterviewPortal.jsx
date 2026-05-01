import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import CameraFeed from "@/components/CameraFeed";
import { validateInterviewToken, completeCandidateInterview, startInterviewFromToken, submitAnswer } from "@/lib/interviewApi";
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
    Volume2,
    ArrowRight,
} from "lucide-react";

/**
 * Public candidate interview portal — no authentication required.
 * Token-based access from HR invitation email.
 * Key design constraint: NO report shown to candidate after completion.
 *
 * Camera is requested when the interview starts (not on the welcome screen)
 * so the permission prompt doesn't surprise the candidate before they've read
 * the instructions.
 */
const CandidateInterviewPortal = () => {
    const { token } = useParams();
    useNavigate();

    // State machine: "loading" → "welcome" → "interview" → "completed" | "error"
    const [phase, setPhase] = useState("loading");
    const [error, setError] = useState("");

    // Interview context
    const [context, setContext]             = useState(null);
    const [sessionId, setSessionId]         = useState(null);
    const [currentQuestion, setCurrentQuestion] = useState("");
    const [questionNumber, setQuestionNumber]   = useState(0);
    const [maxQuestions, setMaxQuestions]       = useState(5);
    const [audioUrl, setAudioUrl]               = useState(null);

    // Recording state
    const [isRecording, setIsRecording]     = useState(false);
    const [mediaRecorder, setMediaRecorder] = useState(null);
    const [isSubmitting, setIsSubmitting]   = useState(false);

    // Camera state (video-only stream, separate from the audio recording)
    const videoRef        = useRef(null);
    const [cameraStream, setCameraStream]   = useState(null);
    const [isCameraOn, setIsCameraOn]       = useState(false);
    const [cameraError, setCameraError]     = useState(null);
    const [isMicOn, setIsMicOn]             = useState(true);

    // Collected evaluations for the final report
    const [evaluations, setEvaluations] = useState([]);

    // Validate token on mount
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

    // Bind video element whenever the camera stream changes
    useEffect(() => {
        if (videoRef.current && cameraStream) {
            videoRef.current.srcObject = cameraStream;
        }
    }, [cameraStream]);

    // Clean up camera tracks when interview ends
    useEffect(() => {
        if (phase === "completed" || phase === "error") {
            if (cameraStream) {
                cameraStream.getTracks().forEach((t) => t.stop());
                setCameraStream(null);
                setIsCameraOn(false);
            }
        }
    }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

    // Start the interview using the candidate's stored CV + JD from Firestore
    const handleStart = async () => {
        setPhase("loading");

        // Request camera access (video-only) — gracefully degrade if denied
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
            });
            setCameraStream(stream);
            setIsCameraOn(true);
        } catch {
            setCameraError("Camera permission denied. The interview will continue without video.");
        }

        // Start the interview session
        try {
            const startData = await startInterviewFromToken(token);
            setSessionId(startData.session_id);
            setCurrentQuestion(startData.question || "Tell me about yourself.");
            setAudioUrl(startData.audio_url || null);
            setMaxQuestions(startData.max_questions || 5);
            setQuestionNumber(1);
            setPhase("interview");
        } catch (err) {
            setError(err.message || "Failed to start the interview. Please try again.");
            setPhase("error");
        }
    };

    // Toggle camera on/off
    const toggleCamera = () => {
        if (!cameraStream) return;
        cameraStream.getVideoTracks().forEach((t) => {
            t.enabled = !t.enabled;
        });
        setIsCameraOn((v) => !v);
    };

    // Recording controls — audio-only, separate from the video stream
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
            const chunks = [];

            recorder.ondataavailable = (e) => chunks.push(e.data);
            recorder.onstop = async () => {
                stream.getTracks().forEach((t) => t.stop());
                const blob = new Blob(chunks, { type: "audio/webm" });
                await handleSubmitAnswer(blob);
            };

            recorder.start();
            setMediaRecorder(recorder);
            setIsRecording(true);
            setIsMicOn(true);
        } catch {
            setError("Microphone access is required for the interview.");
        }
    };

    const stopRecording = () => {
        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
            setIsRecording(false);
        }
    };

    // Submit answer
    const handleSubmitAnswer = async (audioBlob) => {
        setIsSubmitting(true);
        try {
            const result = await submitAnswer(sessionId, audioBlob);

            const newEntry = {
                question: currentQuestion,
                answer: result.transcription || "",
                score: result.feedback?.score || 0,
            };
            const updatedEvals = [...evaluations, newEntry];
            setEvaluations(updatedEvals);

            if (result.status === "completed" || questionNumber >= maxQuestions) {
                const avgScore = updatedEvals.length > 0
                    ? updatedEvals.reduce((sum, e) => sum + (e.score || 0), 0) / updatedEvals.length
                    : 0;

                try {
                    await completeCandidateInterview(token, sessionId, avgScore, {
                        evaluations: updatedEvals,
                        summary:    result.rich_report?.summary    || "",
                        strengths:  result.rich_report?.strengths  || [],
                        weaknesses: result.rich_report?.weaknesses || [],
                    });
                } catch (completeErr) {
                    console.error("Failed to save interview results:", completeErr);
                }

                setPhase("completed");
            } else {
                setCurrentQuestion(result.next_question || result.question || "");
                setAudioUrl(result.audio_url || null);
                setQuestionNumber((n) => n + 1);
                setMaxQuestions(result.max_questions || maxQuestions);
            }
        } catch (err) {
            setError(`Answer submission failed: ${err.message}`);
        } finally {
            setIsSubmitting(false);
        }
    };

    // ─── RENDER ────────────────────────────────────────────────────────────────

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

    if (phase === "loading") {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
            </div>
        );
    }

    if (phase === "welcome") {
        return (
            <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,hsl(221_83%_53%/0.06),transparent_55%)]" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,hsl(160_60%_45%/0.05),transparent_55%)]" />

                <motion.div
                    initial={{ opacity: 0, y: 20, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.5 }}
                    className="relative w-full max-w-lg"
                >
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

    if (phase === "interview") {
        const progressPct = Math.min(((questionNumber - 1) / maxQuestions) * 100, 100);

        return (
            <div className="min-h-screen bg-background">
                {/* Progress bar */}
                <div className="fixed top-0 left-0 right-0 z-50 h-1 bg-muted">
                    <motion.div
                        className="h-full gradient-cobalt"
                        initial={{ width: 0 }}
                        animate={{ width: `${progressPct}%` }}
                        transition={{ duration: 0.5 }}
                    />
                </div>

                <div className="pt-6 pb-12 min-h-screen flex flex-col items-center justify-center p-6 relative">
                    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,hsl(222_80%_6%/0.03),transparent_70%)]" />

                    <div className="relative w-full max-w-3xl space-y-4">
                        {/* Header */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                                <div className="w-8 h-8 rounded-lg gradient-cobalt flex items-center justify-center">
                                    <Brain className="w-4 h-4 text-primary-foreground" />
                                </div>
                                <span className="font-semibold text-foreground">
                                    My<span className="text-gradient-cobalt">HR</span>
                                </span>
                            </div>
                            <span className="text-sm font-medium text-muted-foreground">
                                Question {questionNumber} of {maxQuestions}
                            </span>
                        </div>

                        {/* Split layout: camera left, question right */}
                        <div className="grid md:grid-cols-[2fr_3fr] gap-4">

                            {/* Camera panel */}
                            <div className="flex flex-col gap-3">
                                <div className="aspect-[4/3] rounded-xl overflow-hidden">
                                    <CameraFeed
                                        videoRef={videoRef}
                                        isCameraOn={isCameraOn && !!cameraStream}
                                        error={cameraError}
                                    />
                                </div>

                                {/* Camera error notice */}
                                {cameraError && (
                                    <p className="text-[11px] text-muted-foreground text-center leading-snug">
                                        {cameraError}
                                    </p>
                                )}

                                {/* Camera toggle — only if we have a stream */}
                                {cameraStream && (
                                    <button
                                        onClick={toggleCamera}
                                        className={`w-full flex items-center justify-center gap-2 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                                            isCameraOn
                                                ? "bg-muted border-border text-muted-foreground hover:bg-muted/80"
                                                : "bg-destructive/10 border-destructive/20 text-destructive hover:bg-destructive/20"
                                        }`}
                                    >
                                        {isCameraOn
                                            ? <><Camera className="w-3.5 h-3.5" /> Camera on</>
                                            : <><CameraOff className="w-3.5 h-3.5" /> Camera off</>}
                                    </button>
                                )}
                            </div>

                            {/* Question + recording */}
                            <motion.div
                                key={questionNumber}
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="bg-card rounded-2xl border border-border p-6 space-y-6 shadow-sm flex flex-col"
                            >
                                <p className="text-base font-medium text-foreground leading-relaxed flex-1">
                                    {currentQuestion}
                                </p>

                                {/* Audio playback */}
                                {audioUrl && (
                                    <div className="flex items-center gap-2 text-sm text-cobalt-light">
                                        <Volume2 className="w-4 h-4" />
                                        <audio src={audioUrl} autoPlay controls className="h-8 flex-1" />
                                    </div>
                                )}

                                {/* Recording controls */}
                                <div className="flex flex-col items-center gap-3 pt-2">
                                    {isSubmitting ? (
                                        <div className="flex flex-col items-center gap-2">
                                            <Loader2 className="w-10 h-10 animate-spin text-cobalt" />
                                            <p className="text-sm text-muted-foreground">Processing your answer…</p>
                                        </div>
                                    ) : isRecording ? (
                                        <div className="flex flex-col items-center gap-2">
                                            <button
                                                onClick={stopRecording}
                                                className="relative w-16 h-16 rounded-full bg-destructive flex items-center justify-center shadow-lg hover:bg-destructive/90 transition-colors"
                                            >
                                                <div className="absolute inset-0 rounded-full bg-destructive/30 animate-ping" />
                                                <MicOff className="w-7 h-7 text-white relative z-10" />
                                            </button>
                                            <p className="text-xs text-destructive font-medium">Recording — tap to stop</p>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col items-center gap-2">
                                            <button
                                                onClick={startRecording}
                                                className="w-16 h-16 rounded-full gradient-cobalt flex items-center justify-center shadow-cobalt-lg hover:shadow-cobalt transition-shadow"
                                            >
                                                <Mic className="w-7 h-7 text-white" />
                                            </button>
                                            <p className="text-xs text-muted-foreground">Tap the mic to answer</p>
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // Completed — NO report shown to candidate
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
