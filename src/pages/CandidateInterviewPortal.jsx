import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { validateInterviewToken, completeCandidateInterview, startInterviewFromToken, submitAnswer } from "@/lib/interviewApi";
import {
    Brain,
    Mic,
    MicOff,
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
 */
const CandidateInterviewPortal = () => {
    const { token } = useParams();
    useNavigate(); // keep router context available

    // State machine: "loading" → "welcome" → "interview" → "completed" | "error"
    const [phase, setPhase] = useState("loading");
    const [error, setError] = useState("");

    // Interview context
    const [context, setContext] = useState(null);
    const [sessionId, setSessionId] = useState(null);
    const [currentQuestion, setCurrentQuestion] = useState("");
    const [questionNumber, setQuestionNumber] = useState(0);
    const [maxQuestions, setMaxQuestions] = useState(5);
    const [audioUrl, setAudioUrl] = useState(null);

    // Recording state
    const [isRecording, setIsRecording] = useState(false);
    const [mediaRecorder, setMediaRecorder] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

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

    // Start the interview using the candidate's stored CV + JD from Firestore
    const handleStart = async () => {
        setPhase("loading");
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

    // Recording controls
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
        } catch (err) {
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
                // Compute avgScore from the fully updated list (not stale state)
                const avgScore = updatedEvals.length > 0
                    ? updatedEvals.reduce((sum, e) => sum + (e.score || 0), 0) / updatedEvals.length
                    : 0;

                try {
                    await completeCandidateInterview(token, sessionId, avgScore, {
                        evaluations: updatedEvals,
                        summary: result.report?.summary || "",
                        strengths: result.report?.strengths || [],
                        weaknesses: result.report?.weaknesses || [],
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

    // ─── RENDER ────────────────────────────────────────────────────────────

    // Error state
    if (phase === "error") {
        const isExpired = error.includes("expired");
        return (
            <div className="min-h-screen flex items-center justify-center p-6 bg-background">
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                    className="w-full max-w-sm text-center"
                >
                    <div className="bg-card rounded-2xl border border-border p-8 space-y-5 shadow-sm">
                        <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mx-auto">
                            {isExpired ? <Clock className="w-8 h-8 text-warning" /> : <AlertCircle className="w-8 h-8 text-destructive" />}
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

    // Loading
    if (phase === "loading") {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
            </div>
        );
    }

    // Welcome screen
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
                        {/* Branding */}
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
                            <p className="text-muted-foreground">
                                You've been invited to interview for
                            </p>
                        </div>

                        {/* Context card */}
                        <div className="bg-muted rounded-xl p-5 space-y-2">
                            <p className="font-semibold text-foreground text-lg">{context?.jobTitle || "Position"}</p>
                            <p className="text-sm text-muted-foreground">at {context?.companyName || "Company"}</p>
                        </div>

                        {/* Instructions */}
                        <div className="space-y-3">
                            <p className="text-sm font-medium text-foreground">What to expect:</p>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                {[
                                    "5–7 questions tailored to the job description",
                                    "You'll answer using your microphone",
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

    // Interview in progress
    if (phase === "interview") {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background relative">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,hsl(222_80%_6%/0.03),transparent_70%)]" />

                <div className="relative w-full max-w-2xl space-y-8">
                    {/* Progress */}
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

                    {/* Progress bar */}
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                        <motion.div
                            className="h-full gradient-cobalt rounded-full"
                            initial={{ width: 0 }}
                            animate={{ width: `${(questionNumber / maxQuestions) * 100}%` }}
                            transition={{ duration: 0.5 }}
                        />
                    </div>

                    {/* Question card */}
                    <motion.div
                        key={questionNumber}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-card rounded-2xl border border-border p-8 space-y-6 shadow-sm"
                    >
                        <p className="text-lg font-medium text-foreground leading-relaxed">
                            {currentQuestion}
                        </p>

                        {/* Audio playback */}
                        {audioUrl && (
                            <div className="flex items-center gap-2 text-sm text-cobalt-light">
                                <Volume2 className="w-4 h-4" />
                                <audio src={audioUrl} autoPlay controls className="h-8" />
                            </div>
                        )}

                        {/* Recording controls */}
                        <div className="flex items-center justify-center pt-4">
                            {isSubmitting ? (
                                <div className="flex flex-col items-center gap-2">
                                    <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
                                    <p className="text-sm text-muted-foreground">Processing your answer...</p>
                                </div>
                            ) : isRecording ? (
                                <button
                                    onClick={stopRecording}
                                    className="relative w-20 h-20 rounded-full bg-destructive flex items-center justify-center shadow-lg hover:bg-destructive/90 transition-colors group"
                                >
                                    <div className="absolute inset-0 rounded-full bg-destructive/30 animate-ping" />
                                    <MicOff className="w-8 h-8 text-white relative z-10" />
                                </button>
                            ) : (
                                <button
                                    onClick={startRecording}
                                    className="w-20 h-20 rounded-full gradient-cobalt flex items-center justify-center shadow-cobalt-lg hover:shadow-cobalt transition-shadow group"
                                >
                                    <Mic className="w-8 h-8 text-white group-hover:scale-110 transition-transform" />
                                </button>
                            )}
                        </div>

                        <p className="text-center text-xs text-muted-foreground">
                            {isRecording ? "Click to stop recording" : "Click the mic to start answering"}
                        </p>
                    </motion.div>
                </div>
            </div>
        );
    }

    // Completed — NO report shown
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
                                submitted to the hiring team at <span className="font-medium text-foreground">{context?.companyName}</span>.
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
