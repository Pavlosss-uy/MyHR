import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Link, useLocation, useNavigate } from "react-router-dom";
import Navbar from "@/components/Navbar";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import {
    CheckCircle2,
    AlertCircle,
    ArrowLeft,
    Lightbulb,
    ThumbsUp,
    ThumbsDown,
    BarChart3,
    Loader2,
    Download,
} from "lucide-react";
import { getReport } from "@/lib/interviewApi";

// Persist report to localStorage for the session history list in CandidateHome
const persistReport = (sessionId, report) => {
    try {
        localStorage.setItem(
            `myhr_report_${sessionId}`,
            JSON.stringify({ report, session_id: sessionId, timestamp: Date.now() })
        );
    } catch { /* storage full — non-fatal */ }
};

const FeedbackReport = () => {
    const location  = useLocation();
    const navigate  = useNavigate();
    const routeState = location.state;

    const [report,   setReport]   = useState(null);
    const [loading,  setLoading]  = useState(true);
    const [error,    setError]    = useState("");

    useEffect(() => {
        (async () => {
            // ① Report passed directly from InterviewRoom (completed or early-ended)
            if (routeState?.report) {
                const evaluations = routeState.report;
                const built = {
                    evaluations,
                    average_score: evaluations.length
                        ? Math.round(evaluations.reduce((s, e) => s + (e.score || 0), 0) / evaluations.length)
                        : 0,
                    total_questions: evaluations.length,
                    job_title: routeState.job_title || "Interview",
                    candidate_name: routeState.candidate_name || "Candidate",
                };
                if (routeState.session_id) persistReport(routeState.session_id, evaluations);
                setReport(built);
                setLoading(false);
                return;
            }

            // ② Try to load from localStorage cache (e.g. navigated directly)
            if (routeState?.session_id) {
                try {
                    const cached = localStorage.getItem(`myhr_report_${routeState.session_id}`);
                    if (cached) {
                        const parsed = JSON.parse(cached);
                        const evaluations = parsed.report || [];
                        setReport({
                            evaluations,
                            average_score: evaluations.length
                                ? Math.round(evaluations.reduce((s, e) => s + (e.score || 0), 0) / evaluations.length)
                                : 0,
                            total_questions: evaluations.length,
                            job_title: "Mock Interview",
                            candidate_name: "Candidate",
                        });
                        setLoading(false);
                        return;
                    }
                } catch { /* ignore */ }

                // ③ Fetch from backend as fallback
                try {
                    const data = await getReport(routeState.session_id);
                    if (data.evaluations) persistReport(routeState.session_id, data.evaluations);
                    setReport(data);
                } catch (err) {
                    setError(err.message || "Failed to load report.");
                }
                setLoading(false);
                return;
            }

            // No data at all
            setLoading(false);
        })();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Loading ───────────────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <div className="pt-32 flex flex-col items-center justify-center gap-3">
                    <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
                    <p className="text-sm text-muted-foreground">Loading your report…</p>
                </div>
            </div>
        );
    }

    // ── Error / empty ─────────────────────────────────────────────────────────
    if (error || !report) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <main className="pt-24 pb-12 max-w-5xl mx-auto px-6 text-center">
                    <h1 className="text-2xl font-bold text-foreground mb-4">No Report Available</h1>
                    <p className="text-muted-foreground mb-6">
                        {error || "Complete an interview to see your feedback report."}
                    </p>
                    <Button asChild>
                        <Link to="/candidate">Go to Dashboard</Link>
                    </Button>
                </main>
            </div>
        );
    }

    const evaluations = report.evaluations || [];
    const avgScore    = report.average_score || 0;
    const strengths   = evaluations.filter((e) => e.score >= 70);
    const improvements = evaluations.filter((e) => e.score < 70);

    const scoreColor = avgScore >= 80 ? "mint" : avgScore >= 60 ? "cobalt" : "warning";
    const scoreLabel = avgScore >= 80 ? "Excellent" : avgScore >= 60 ? "Good" : "Needs Work";

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-5xl mx-auto px-6">

                {/* Page header */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8 flex items-center justify-between flex-wrap gap-4"
                >
                    <div>
                        <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
                            <Link to="/candidate">
                                <ArrowLeft className="w-4 h-4 mr-1" />
                                Back to Dashboard
                            </Link>
                        </Button>
                        <h1 className="text-2xl font-bold text-foreground">AI Feedback Report</h1>
                        <p className="text-muted-foreground mt-1">
                            {report.job_title} — {report.total_questions} question{report.total_questions !== 1 ? "s" : ""} answered
                        </p>
                    </div>
                </motion.div>

                {/* Score overview */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="bg-card rounded-xl border border-border shadow-sm p-8 mb-6"
                >
                    <div className="flex flex-col md:flex-row items-center gap-8">
                        <CircularProgress
                            value={avgScore}
                            size={140}
                            strokeWidth={10}
                            label="Overall Score"
                            sublabel={scoreLabel}
                            color={scoreColor}
                        />
                        <div className="flex-1 w-full">
                            <h3 className="font-semibold text-foreground mb-4">Question Scores</h3>
                            <div className="space-y-3">
                                {evaluations.map((e, idx) => (
                                    <div key={idx} className="flex items-center gap-3">
                                        <span className="text-xs text-muted-foreground w-8 shrink-0">Q{idx + 1}</span>
                                        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${e.score}%` }}
                                                transition={{ delay: 0.2 + idx * 0.08, duration: 0.5 }}
                                                className={`h-full rounded-full ${
                                                    e.score >= 80
                                                        ? "bg-mint"
                                                        : e.score >= 60
                                                        ? "gradient-cobalt"
                                                        : "bg-warning"
                                                }`}
                                            />
                                        </div>
                                        <span className="text-sm font-semibold text-foreground w-10 text-right">
                                            {e.score}%
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Detailed Q&A breakdown */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="bg-card rounded-xl border border-border shadow-sm mb-6"
                >
                    <div className="p-5 border-b border-border flex items-center gap-2">
                        <BarChart3 className="w-5 h-5 text-cobalt" />
                        <h3 className="font-semibold text-foreground">Detailed Breakdown</h3>
                    </div>
                    <div className="divide-y divide-border">
                        {evaluations.map((e, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: 0.3 + idx * 0.05 }}
                                className="p-5"
                            >
                                <div className="flex items-start justify-between gap-4 mb-3">
                                    <div className="flex-1">
                                        <p className="text-sm font-medium text-foreground mb-1">
                                            Q{idx + 1}: {e.question}
                                        </p>
                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                            <span className="font-medium text-foreground/70">Answer: </span>
                                            {e.answer || <em className="text-muted-foreground/50">No answer recorded</em>}
                                        </p>
                                    </div>
                                    <div
                                        className={`px-3 py-1.5 rounded-lg text-sm font-bold shrink-0 ${
                                            e.score >= 80
                                                ? "bg-mint/10 text-mint"
                                                : e.score >= 60
                                                ? "bg-cobalt/10 text-cobalt-lighter"
                                                : "bg-warning/10 text-warning"
                                        }`}
                                    >
                                        {e.score}%
                                    </div>
                                </div>
                                {e.feedback && (
                                    <div className="flex items-start gap-2 mt-2 pl-2 border-l-2 border-cobalt/20">
                                        <Lightbulb className="w-3.5 h-3.5 text-cobalt-lighter mt-0.5 shrink-0" />
                                        <p className="text-xs text-muted-foreground leading-relaxed">{e.feedback}</p>
                                    </div>
                                )}
                            </motion.div>
                        ))}
                    </div>
                </motion.div>

                {/* Strengths & improvements */}
                <div className="grid md:grid-cols-2 gap-6 mb-8">
                    {strengths.length > 0 && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.35 }}
                            className="bg-card rounded-xl border border-border shadow-sm"
                        >
                            <div className="p-5 border-b border-border flex items-center gap-2">
                                <CheckCircle2 className="w-5 h-5 text-mint" />
                                <h3 className="font-semibold text-foreground">Strong Answers</h3>
                            </div>
                            <div className="p-5 space-y-3">
                                {strengths.map((s, i) => (
                                    <div key={i} className="flex items-start gap-3">
                                        <ThumbsUp className="w-4 h-4 text-mint mt-0.5 shrink-0" />
                                        <div>
                                            <p className="text-sm font-medium text-foreground">Score: {s.score}%</p>
                                            <p className="text-xs text-muted-foreground">{s.feedback}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    )}

                    {improvements.length > 0 && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.4 }}
                            className="bg-card rounded-xl border border-border shadow-sm"
                        >
                            <div className="p-5 border-b border-border flex items-center gap-2">
                                <AlertCircle className="w-5 h-5 text-warning" />
                                <h3 className="font-semibold text-foreground">Areas to Improve</h3>
                            </div>
                            <div className="p-5 space-y-3">
                                {improvements.map((w, i) => (
                                    <div key={i} className="flex items-start gap-3">
                                        <ThumbsDown className="w-4 h-4 text-warning mt-0.5 shrink-0" />
                                        <div>
                                            <p className="text-sm font-medium text-foreground">Score: {w.score}%</p>
                                            <p className="text-xs text-muted-foreground">{w.feedback}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    )}
                </div>

                {/* CTA */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.45 }}
                    className="flex justify-center gap-4"
                >
                    <Button variant="hero" size="lg" asChild>
                        <Link to="/candidate">Practice Again</Link>
                    </Button>
                </motion.div>
            </main>
        </div>
    );
};

export default FeedbackReport;
