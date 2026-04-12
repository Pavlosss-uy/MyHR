import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
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
    BookOpen,
    Target,
    TrendingUp,
    Award,
    HelpCircle,
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

// ── Small UI helpers ─────────────────────────────────────────────────────────

const PerformanceBadge = ({ level }) => {
    const styles = {
        "Excellent":     "bg-mint/15 text-mint border-mint/30",
        "Good":          "bg-cobalt/15 text-cobalt-lighter border-cobalt/30",
        "Average":       "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
        "Below Average": "bg-orange-500/15 text-orange-400 border-orange-500/30",
        "Poor":          "bg-warning/15 text-warning border-warning/30",
    };
    return (
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${styles[level] || styles["Average"]}`}>
            {level}
        </span>
    );
};

const HiringBadge = ({ signal }) => {
    const styles = {
        "Strong Yes": "bg-mint/15 text-mint border-mint/30",
        "Yes":        "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
        "Maybe":      "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
        "No":         "bg-orange-500/15 text-orange-400 border-orange-500/30",
        "Strong No":  "bg-warning/15 text-warning border-warning/30",
    };
    return (
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold border ${styles[signal] || styles["Maybe"]}`}>
            <Award className="w-3.5 h-3.5" />
            Hiring Signal: {signal}
        </span>
    );
};

const SectionHeader = ({ icon: Icon, label, color = "text-cobalt" }) => (
    <div className="p-5 border-b border-border flex items-center gap-2">
        <Icon className={`w-5 h-5 ${color}`} />
        <h3 className="font-semibold text-foreground">{label}</h3>
    </div>
);

// ── Main Component ───────────────────────────────────────────────────────────

const FeedbackReport = () => {
    const location   = useLocation();
    const routeState = location.state;

    const [report,     setReport]     = useState(null);
    const [richReport, setRichReport] = useState(null);
    const [loading,    setLoading]    = useState(true);
    const [error,      setError]      = useState("");

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
                if (routeState.rich_report) setRichReport(routeState.rich_report);
                setLoading(false);
                return;
            }

            // ② Try to load from localStorage cache
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
                    if (data.status === "incomplete") {
                        setError(data.message || "Interview ended too early to generate a report.");
                        setLoading(false);
                        return;
                    }
                    if (data.evaluations) persistReport(routeState.session_id, data.evaluations);
                    setReport(data);
                    if (data.rich_report) setRichReport(data.rich_report);
                } catch (err) {
                    setError(err.message || "Failed to load report.");
                }
                setLoading(false);
                return;
            }

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

    const evaluations  = report.evaluations || [];
    const avgScore     = report.average_score || 0;
    const scoreColor   = avgScore >= 80 ? "mint" : avgScore >= 60 ? "cobalt" : "warning";
    const scoreLabel   = avgScore >= 80 ? "Excellent" : avgScore >= 60 ? "Good" : "Needs Work";

    // Rich report fields (may be null if synthesis failed)
    const rr = richReport || {};
    const strengths      = rr.strengths      || [];
    const weaknesses     = rr.weaknesses     || [];
    const improvements   = rr.improvements   || [];
    const tips           = rr.tips           || [];
    const recTopics      = rr.recommended_topics || [];

    // Fallback strength/weakness lists from raw scores if no rich report
    const fallbackStrengths    = evaluations.filter((e) => e.score >= 70);
    const fallbackImprovements = evaluations.filter((e) => e.score < 70);

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-5xl mx-auto px-6">

                {/* ── Page header ─────────────────────────────────────────── */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8 flex items-start justify-between flex-wrap gap-4"
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
                    <div className="flex flex-col items-end gap-2 pt-8">
                        {rr.performance_level && <PerformanceBadge level={rr.performance_level} />}
                        {rr.hiring_signal     && <HiringBadge signal={rr.hiring_signal} />}
                    </div>
                </motion.div>

                {/* ── Score overview ───────────────────────────────────────── */}
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
                            {rr.summary && (
                                <p className="text-sm text-muted-foreground leading-relaxed mb-4 italic">
                                    {rr.summary}
                                </p>
                            )}
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

                {/* ── Detailed Q&A breakdown ───────────────────────────────── */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="bg-card rounded-xl border border-border shadow-sm mb-6"
                >
                    <SectionHeader icon={BarChart3} label="Detailed Breakdown" />
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

                {/* ── Rich report: Strengths ───────────────────────────────── */}
                {strengths.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.35 }}
                        className="bg-card rounded-xl border border-border shadow-sm mb-6"
                    >
                        <SectionHeader icon={CheckCircle2} label="Strengths" color="text-mint" />
                        <div className="p-5 space-y-4">
                            {strengths.map((s, i) => (
                                <div key={i} className="flex items-start gap-3">
                                    <ThumbsUp className="w-4 h-4 text-mint mt-0.5 shrink-0" />
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{s.area}</p>
                                        {s.evidence && (
                                            <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                                                <span className="font-medium text-foreground/60">Evidence: </span>
                                                {s.evidence}
                                            </p>
                                        )}
                                        {s.impact && (
                                            <p className="text-xs text-mint/80 mt-0.5 leading-relaxed">
                                                <span className="font-medium">Why it matters: </span>
                                                {s.impact}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* Fallback strengths when no rich report */}
                {strengths.length === 0 && fallbackStrengths.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.35 }}
                        className="bg-card rounded-xl border border-border shadow-sm mb-6"
                    >
                        <SectionHeader icon={CheckCircle2} label="Strong Answers" color="text-mint" />
                        <div className="p-5 space-y-3">
                            {fallbackStrengths.map((s, i) => (
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

                {/* ── Rich report: Weaknesses ──────────────────────────────── */}
                {weaknesses.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="bg-card rounded-xl border border-border shadow-sm mb-6"
                    >
                        <SectionHeader icon={AlertCircle} label="Areas to Improve" color="text-warning" />
                        <div className="p-5 space-y-4">
                            {weaknesses.map((w, i) => (
                                <div key={i} className="flex items-start gap-3">
                                    <ThumbsDown className="w-4 h-4 text-warning mt-0.5 shrink-0" />
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{w.area}</p>
                                        {w.evidence && (
                                            <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                                                <span className="font-medium text-foreground/60">Evidence: </span>
                                                {w.evidence}
                                            </p>
                                        )}
                                        {w.impact && (
                                            <p className="text-xs text-warning/80 mt-0.5 leading-relaxed">
                                                <span className="font-medium">Impact: </span>
                                                {w.impact}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* Fallback weaknesses when no rich report */}
                {weaknesses.length === 0 && fallbackImprovements.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="bg-card rounded-xl border border-border shadow-sm mb-6"
                    >
                        <SectionHeader icon={AlertCircle} label="Areas to Improve" color="text-warning" />
                        <div className="p-5 space-y-3">
                            {fallbackImprovements.map((w, i) => (
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

                {/* ── Rich report: Improvements (WHAT / WHY / HOW) ────────── */}
                {improvements.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.45 }}
                        className="bg-card rounded-xl border border-border shadow-sm mb-6"
                    >
                        <SectionHeader icon={TrendingUp} label="How to Improve" color="text-cobalt-lighter" />
                        <div className="divide-y divide-border">
                            {improvements.map((imp, i) => (
                                <div key={i} className="p-5">
                                    <p className="text-sm font-semibold text-foreground mb-3">
                                        {imp.weakness_area}
                                    </p>
                                    <div className="space-y-2.5">
                                        {imp.what_is_wrong && (
                                            <div className="flex items-start gap-2.5">
                                                <span className="text-xs font-bold text-warning/80 w-10 pt-0.5 shrink-0">WHAT</span>
                                                <p className="text-xs text-muted-foreground leading-relaxed">{imp.what_is_wrong}</p>
                                            </div>
                                        )}
                                        {imp.why_it_matters && (
                                            <div className="flex items-start gap-2.5">
                                                <span className="text-xs font-bold text-cobalt-lighter/80 w-10 pt-0.5 shrink-0">WHY</span>
                                                <p className="text-xs text-muted-foreground leading-relaxed">{imp.why_it_matters}</p>
                                            </div>
                                        )}
                                        {imp.how_to_improve && (
                                            <div className="flex items-start gap-2.5">
                                                <span className="text-xs font-bold text-mint/80 w-10 pt-0.5 shrink-0">HOW</span>
                                                <p className="text-xs text-muted-foreground leading-relaxed">{imp.how_to_improve}</p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* ── Tips ────────────────────────────────────────────────── */}
                {tips.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.5 }}
                        className="bg-card rounded-xl border border-border shadow-sm mb-6"
                    >
                        <SectionHeader icon={Lightbulb} label="Interview Tips" color="text-yellow-400" />
                        <div className="p-5 space-y-3">
                            {tips.map((t, i) => (
                                <div key={i} className="flex items-start gap-3">
                                    <div className="shrink-0 mt-0.5 px-2 py-0.5 rounded text-xs font-semibold bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                                        {t.category}
                                    </div>
                                    <p className="text-xs text-muted-foreground leading-relaxed">{t.tip}</p>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* ── Recommended topics ───────────────────────────────────── */}
                {recTopics.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.55 }}
                        className="bg-card rounded-xl border border-border shadow-sm mb-8"
                    >
                        <SectionHeader icon={BookOpen} label="Recommended Study Topics" color="text-cobalt" />
                        <div className="p-5 flex flex-wrap gap-2">
                            {recTopics.map((topic, i) => (
                                <span
                                    key={i}
                                    className="px-3 py-1.5 rounded-full text-xs font-medium bg-cobalt/10 text-cobalt-lighter border border-cobalt/20"
                                >
                                    {topic}
                                </span>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* ── CTA ─────────────────────────────────────────────────── */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.6 }}
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
