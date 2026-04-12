import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import Navbar from "@/components/Navbar";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import {
    Mic,
    Clock,
    TrendingUp,
    Trophy,
    ArrowRight,
    Play,
    Star,
    Upload,
    FileText,
    X,
    Loader2,
    History,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { startInterview } from "@/lib/interviewApi";

// Read ALL completed interview sessions from localStorage (written by InterviewRoom after each completion).
// Returns the full sorted list — callers slice for display as needed.
const loadSessionHistory = () => {
    try {
        const keys = Object.keys(localStorage).filter((k) => k.startsWith("myhr_report_"));
        return keys
            .map((k) => {
                try { return JSON.parse(localStorage.getItem(k)); } catch { return null; }
            })
            .filter(Boolean)
            .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    } catch {
        return [];
    }
};

const CandidateHome = () => {
    const { user } = useAuth();
    const navigate  = useNavigate();
    const firstName = user?.displayName?.split(" ")[0] || user?.email?.split("@")[0] || "there";

    // allHistory = every session (for accurate counts and averages)
    // history    = last 4 only (for the display list)
    const allHistory = useMemo(() => loadSessionHistory(), []);
    const history    = useMemo(() => allHistory.slice(0, 4), [allHistory]);

    // Derived stats from the FULL history, not the truncated display list
    const totalInterviews = allHistory.length;
    const avgScore = totalInterviews > 0
        ? Math.round(allHistory.reduce((sum, s) => sum + (s.report?.reduce((a, e) => a + (e.score || 0), 0) / (s.report?.length || 1)), 0) / totalInterviews)
        : 0;
    const readiness = Math.min(100, avgScore > 0 ? avgScore : 0);

    // Setup modal
    const [showSetup,  setShowSetup]  = useState(false);
    const [cvFile,     setCvFile]     = useState(null);
    const [jdText,     setJdText]     = useState("");
    const [isStarting, setIsStarting] = useState(false);
    const [setupError, setSetupError] = useState("");

    const handleStartInterview = async () => {
        if (!cvFile || !jdText.trim()) {
            setSetupError("Please upload a CV and enter a job description.");
            return;
        }
        setSetupError("");
        setIsStarting(true);
        try {
            const data = await startInterview(cvFile, jdText);
            navigate("/interview", {
                state: { session_id: data.session_id, question: data.question, audio_url: data.audio_url },
            });
        } catch (err) {
            setSetupError(err.message || "Failed to start interview. Make sure the backend is running.");
            setIsStarting(false);
        }
    };

    const closeSetup = () => { setShowSetup(false); setSetupError(""); setCvFile(null); setJdText(""); };

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-6xl mx-auto px-6">

                {/* Header */}
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
                    <h1 className="text-2xl font-bold text-foreground">Welcome back, {firstName} 👋</h1>
                    <p className="text-muted-foreground mt-1">
                        {totalInterviews > 0
                            ? `You've completed ${totalInterviews} interview${totalInterviews > 1 ? "s" : ""}. Keep practising!`
                            : "Start your first AI mock interview to begin tracking your progress."}
                    </p>
                </motion.div>

                <div className="grid lg:grid-cols-3 gap-6">
                    {/* ── Left column ── */}
                    <div className="lg:col-span-2 space-y-6">

                        {/* CTA card */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.1 }}
                            className="gradient-cobalt rounded-2xl p-8 shadow-cobalt-lg"
                        >
                            <h2 className="text-xl font-bold text-primary-foreground mb-2">Ready for your next practice?</h2>
                            <p className="text-cobalt-lighter mb-6">Jump into an AI-powered mock interview and improve your skills.</p>
                            <div className="flex gap-3 flex-wrap">
                                <Button
                                    size="lg"
                                    className="bg-card text-primary hover:bg-card/90 shadow-lg"
                                    onClick={() => setShowSetup(true)}
                                >
                                    <Mic className="w-4 h-4 mr-2" />
                                    Start Mock Interview
                                </Button>
                                {history.length > 0 && (
                                    <Button
                                        variant="ghost"
                                        size="lg"
                                        className="text-primary-foreground border border-primary-foreground/20 hover:bg-primary-foreground/10"
                                        onClick={() => navigate("/feedback", { state: { session_id: history[0].session_id, report: history[0].report, rich_report: history[0].rich_report ?? null } })}
                                    >
                                        View Last Report
                                    </Button>
                                )}
                            </div>
                        </motion.div>

                        {/* Stats */}
                        <div className="grid sm:grid-cols-3 gap-4">
                            {[
                                { label: "Total Interviews", value: totalInterviews || "—", icon: Mic,         color: "cobalt",   delay: 0.15 },
                                { label: "Avg. Score",       value: avgScore ? `${avgScore}%` : "—", icon: TrendingUp, color: "mint",    delay: 0.2  },
                                { label: "Sessions",         value: totalInterviews || "—", icon: Clock,        color: "warning",  delay: 0.25 },
                            ].map(({ label, value, icon: Icon, color, delay }) => (
                                <motion.div
                                    key={label}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay }}
                                    className="bg-card rounded-xl border border-border p-5"
                                >
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className={`w-9 h-9 rounded-lg bg-${color}/10 flex items-center justify-center`}>
                                            <Icon className={`w-4 h-4 text-${color}`} />
                                        </div>
                                        <span className="text-sm text-muted-foreground">{label}</span>
                                    </div>
                                    <p className="text-2xl font-bold text-foreground">{value}</p>
                                </motion.div>
                            ))}
                        </div>

                        {/* Session history */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            className="bg-card rounded-xl border border-border shadow-sm"
                        >
                            <div className="p-5 border-b border-border flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <History className="w-4 h-4 text-cobalt" />
                                    <h3 className="font-semibold text-foreground">Past Mock Interviews</h3>
                                </div>
                            </div>

                            {history.length === 0 ? (
                                <div className="px-5 py-10 text-center">
                                    <p className="text-muted-foreground text-sm">No interviews yet.</p>
                                    <button
                                        onClick={() => setShowSetup(true)}
                                        className="mt-3 text-sm text-cobalt-light hover:text-cobalt font-medium transition-colors"
                                    >
                                        Start your first interview →
                                    </button>
                                </div>
                            ) : (
                                <div className="divide-y divide-border">
                                    {history.map((session) => {
                                        const score = session.report
                                            ? Math.round(session.report.reduce((s, e) => s + (e.score || 0), 0) / session.report.length)
                                            : null;
                                        const date = session.timestamp
                                            ? new Date(session.timestamp).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
                                            : "—";
                                        return (
                                            <div
                                                key={session.session_id}
                                                className="px-5 py-4 flex items-center justify-between hover:bg-muted/30 transition-colors"
                                            >
                                                <div className="flex items-center gap-4">
                                                    <div className="w-10 h-10 rounded-lg bg-primary/5 flex items-center justify-center">
                                                        <Play className="w-4 h-4 text-primary" />
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-medium text-foreground">
                                                            Interview Session
                                                        </p>
                                                        <p className="text-xs text-muted-foreground">{date}</p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4">
                                                    {score != null && (
                                                        <div className="flex items-center gap-1">
                                                            <Star className="w-3.5 h-3.5 text-warning fill-warning" />
                                                            <span className="text-sm font-semibold text-foreground">{score}%</span>
                                                        </div>
                                                    )}
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => navigate("/feedback", { state: { session_id: session.session_id, report: session.report, rich_report: session.rich_report ?? null } })}
                                                    >
                                                        <ArrowRight className="w-4 h-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </motion.div>
                    </div>

                    {/* ── Right column ── */}
                    <div className="space-y-6">
                        {/* Readiness */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.2 }}
                            className="bg-card rounded-xl border border-border shadow-sm p-6 text-center"
                        >
                            <h3 className="font-semibold text-foreground mb-6">Interview Readiness</h3>
                            <CircularProgress
                                value={readiness}
                                size={160}
                                strokeWidth={10}
                                color={readiness >= 80 ? "mint" : readiness >= 60 ? "cobalt" : "warning"}
                            />
                            <p className="text-sm text-muted-foreground mt-4">
                                {readiness === 0
                                    ? "Complete your first interview to see your score."
                                    : "Based on your average interview score."}
                            </p>
                            <Button variant="hero" size="sm" className="mt-4 w-full" onClick={() => setShowSetup(true)}>
                                {totalInterviews === 0 ? "Start First Interview" : "Practice Again"}
                            </Button>
                        </motion.div>

                        {/* Achievements */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            className="bg-card rounded-xl border border-border shadow-sm p-6"
                        >
                            <div className="flex items-center gap-2 mb-4">
                                <Trophy className="w-5 h-5 text-warning" />
                                <h3 className="font-semibold text-foreground">Achievements</h3>
                            </div>
                            <div className="space-y-3">
                                {[
                                    { label: "First Interview",  done: totalInterviews >= 1  },
                                    { label: "Score 80+",        done: avgScore >= 80         },
                                    { label: "5 Interviews",     done: totalInterviews >= 5  },
                                    { label: "Score 95+",        done: avgScore >= 95         },
                                    { label: "10 Interviews",    done: totalInterviews >= 10 },
                                ].map((a) => (
                                    <div key={a.label} className="flex items-center gap-3">
                                        <div className={`w-6 h-6 rounded-full flex items-center justify-center ${a.done ? "bg-mint/20" : "bg-muted"}`}>
                                            {a.done
                                                ? <Trophy className="w-3 h-3 text-mint" />
                                                : <div className="w-2 h-2 rounded-full bg-muted-foreground/30" />}
                                        </div>
                                        <span className={`text-sm ${a.done ? "text-foreground font-medium" : "text-muted-foreground"}`}>
                                            {a.label}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    </div>
                </div>
            </main>

            {/* ── Interview Setup Modal ─────────────────────────────────────────── */}
            {showSetup && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        className="bg-card rounded-2xl border border-border shadow-2xl max-w-lg w-full p-8"
                    >
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-foreground">Setup Interview</h2>
                            <button
                                onClick={closeSetup}
                                className="w-8 h-8 rounded-full flex items-center justify-center text-muted-foreground hover:bg-muted transition-colors"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* CV upload */}
                        <div className="mb-5">
                            <label className="block text-sm font-medium text-foreground mb-2">Upload CV (PDF)</label>
                            <label className="flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-dashed border-border hover:border-cobalt/40 cursor-pointer transition-colors bg-muted/30">
                                <Upload className="w-5 h-5 text-muted-foreground" />
                                <span className="text-sm text-muted-foreground">
                                    {cvFile ? cvFile.name : "Click to choose a PDF file"}
                                </span>
                                <input
                                    type="file"
                                    accept=".pdf"
                                    className="hidden"
                                    onChange={(e) => { setCvFile(e.target.files[0] || null); setSetupError(""); }}
                                />
                            </label>
                            {cvFile && (
                                <div className="flex items-center gap-2 mt-2 text-xs text-mint">
                                    <FileText className="w-3.5 h-3.5" />
                                    {cvFile.name} ({Math.round(cvFile.size / 1024)} KB)
                                </div>
                            )}
                        </div>

                        {/* Job description */}
                        <div className="mb-6">
                            <label className="block text-sm font-medium text-foreground mb-2">Job Description</label>
                            <textarea
                                value={jdText}
                                onChange={(e) => { setJdText(e.target.value); setSetupError(""); }}
                                placeholder="Paste the job description here…"
                                rows={5}
                                className="w-full px-4 py-3 rounded-xl border border-border bg-muted/30 text-foreground text-sm placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-cobalt/40 focus:border-cobalt/40 resize-none"
                            />
                        </div>

                        {setupError && <p className="text-sm text-destructive mb-4">{setupError}</p>}

                        <div className="flex gap-3">
                            <Button
                                variant="hero"
                                size="lg"
                                className="flex-1"
                                onClick={handleStartInterview}
                                disabled={isStarting}
                            >
                                {isStarting ? (
                                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Initializing AI Agent…</>
                                ) : (
                                    <><Mic className="w-4 h-4 mr-2" /> Start Interview</>
                                )}
                            </Button>
                            <Button variant="outline" size="lg" onClick={closeSetup} disabled={isStarting}>
                                Cancel
                            </Button>
                        </div>
                    </motion.div>
                </div>
            )}
        </div>
    );
};

export default CandidateHome;
