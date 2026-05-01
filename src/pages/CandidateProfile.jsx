import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Navbar from "@/components/Navbar";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import { getCandidate } from "@/lib/interviewApi";
import {
    ArrowLeft, Mail, Phone, Briefcase, Star, CheckCircle2, AlertCircle,
    Loader2, Brain, XCircle, Mic, BarChart3, Send, ThumbsUp, ThumbsDown,
    Lightbulb, TrendingUp, BookOpen, Award,
} from "lucide-react";
import {
    PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

// ── Helpers ───────────────────────────────────────────────────────────────────

const getRecommendation = (score) => {
    if (score >= 85) return { label: "Strong Hire", color: "bg-mint/10 text-mint-dark border-mint/20" };
    if (score >= 70) return { label: "Hire",        color: "bg-cobalt/10 text-cobalt border-cobalt/20" };
    if (score >= 55) return { label: "Consider",    color: "bg-warning/10 text-warning border-warning/20" };
    return              { label: "No Hire",          color: "bg-destructive/10 text-destructive border-destructive/20" };
};

const PerformanceBadge = ({ level }) => {
    const styles = {
        "Excellent":         "bg-mint/15 text-mint border-mint/30",
        "Good":              "bg-cobalt/15 text-cobalt border-cobalt/30",
        "Needs Improvement": "bg-yellow-500/15 text-yellow-600 border-yellow-500/30",
        "Below Average":     "bg-orange-500/15 text-orange-500 border-orange-500/30",
        "Poor":              "bg-warning/15 text-warning border-warning/30",
    };
    return (
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${styles[level] || styles["Needs Improvement"]}`}>
            {level}
        </span>
    );
};

const HiringBadge = ({ signal }) => {
    const norm = !signal ? "Borderline"
        : signal === "Strong Yes" || signal === "Yes" ? "Yes"
        : signal === "Strong No"  || signal === "No"  ? "No"
        : "Borderline";
    const styles = {
        "Yes":        "bg-mint/15 text-mint border-mint/30",
        "Borderline": "bg-yellow-500/15 text-yellow-600 border-yellow-500/30",
        "No":         "bg-warning/15 text-warning border-warning/30",
    };
    return (
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold border ${styles[norm]}`}>
            <Award className="w-3.5 h-3.5" />
            Hiring Signal: {norm}
        </span>
    );
};

const SectionHeader = ({ icon: Icon, label, color = "text-cobalt" }) => (
    <div className="p-5 border-b border-border flex items-center gap-2">
        <Icon className={`w-5 h-5 ${color}`} />
        <h3 className="font-semibold text-foreground">{label}</h3>
    </div>
);

const TONE_PALETTE = ["#6366f1","#10b981","#f59e0b","#3b82f6","#8b5cf6","#ef4444","#f97316","#06b6d4"];
const getToneColor = (emotion, i) => ({
    confident:"#6366f1", engaged:"#6366f1", calm:"#10b981", happy:"#10b981",
    hesitant:"#f59e0b", uncertain:"#f59e0b", neutral:"#3b82f6",
    enthusiastic:"#8b5cf6", nervous:"#ef4444", frustrated:"#f97316", surprised:"#06b6d4",
}[emotion?.toLowerCase()] ?? TONE_PALETTE[i % TONE_PALETTE.length]);

const ToneTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    return (
        <div className="bg-card border border-border rounded-lg px-3 py-2 shadow-lg text-xs">
            <p className="font-semibold text-foreground capitalize">{payload[0].name}</p>
            <p className="text-muted-foreground">{payload[0].value.toFixed(1)}%</p>
        </div>
    );
};

const ToneLegend = ({ payload }) => (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5 mt-3">
        {(payload || []).map((e, i) => (
            <div key={i} className="flex items-center gap-1.5">
                <span className="inline-block w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: e.color }} />
                <span className="text-xs text-muted-foreground capitalize">{e.value}</span>
            </div>
        ))}
    </div>
);

const safeStr = (v) => typeof v === "string" ? v : (v?.text || v?.area || v?.description || JSON.stringify(v));

// ── Main Component ────────────────────────────────────────────────────────────

const CandidateProfile = () => {
    const { id } = useParams();
    const [searchParams] = useSearchParams();
    const jobId = searchParams.get("jobId") || "";

    const [candidate, setCandidate] = useState(null);
    const [loading, setLoading]     = useState(true);
    const [error, setError]         = useState("");

    useEffect(() => {
        if (!jobId || !id) { setError("Missing job or candidate reference."); setLoading(false); return; }
        (async () => {
            try {
                const data = await getCandidate(jobId, id);
                setCandidate(data);
            } catch (err) {
                setError(err.message || "Failed to load candidate.");
            } finally {
                setLoading(false);
            }
        })();
    }, [id, jobId]);

    if (loading) return (
        <div className="min-h-screen bg-background flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
        </div>
    );

    if (error || !candidate) return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-5xl mx-auto px-6 text-center">
                <p className="text-muted-foreground">{error || "Candidate not found."}</p>
                <Button variant="outline" className="mt-4" asChild>
                    <Link to="/hr/dashboard">Back to Dashboard</Link>
                </Button>
            </main>
        </div>
    );

    const rec     = getRecommendation(candidate.totalScore || candidate.matchScore || 0);
    const matched = candidate.matchDetails?.matched || [];
    const missing = candidate.matchDetails?.missing || [];
    const extra   = candidate.matchDetails?.extra   || [];

    // Rich report — enriched by backend from the JSON file
    const ir = candidate.interviewReport || {};

    // Q&A source: prefer question_scores (richer) from rich_report, fallback to evaluations
    const questionScores = ir.question_scores?.length > 0 ? ir.question_scores : (ir.evaluations || []);
    const avgScore = ir.overall_score
        || (questionScores.length ? Math.round(questionScores.reduce((s, e) => s + (e.score || 0), 0) / questionScores.length) : 0);
    const scoreColor = avgScore >= 80 ? "mint" : avgScore >= 60 ? "cobalt" : "warning";
    const scoreLabel = avgScore >= 80 ? "Excellent" : avgScore >= 60 ? "Good" : "Needs Work";

    const strengths    = ir.strengths || [];
    const weaknesses   = ir.areas_to_improve || ir.weaknesses || [];
    const improvements = ir.how_to_improve   || ir.improvements || [];
    const tips         = ir.tips || [];
    const recTopics    = ir.recommended_topics || [];

    // Fallbacks from question scores
    const fallbackStrengths    = questionScores.filter(e => e.score >= 70);
    const fallbackImprovements = questionScores.filter(e => e.score < 70);

    // Tone analysis
    const ca   = ir.tone_analysis || ir.communication_analysis || {};
    const comm = ir.communication || {};
    const dominantTone    = ca.overall_tone      || comm.tone       || null;
    const confidenceLevel = ca.confidence_level  || comm.confidence || null;
    const clarityLevel    = ca.clarity_of_speech || comm.clarity    || null;
    const toneEffective   = ca.tone_effectiveness || null;
    const observations    = ca.observations    || (comm.feedback ? [comm.feedback] : []);
    const recommendations = ca.recommendations || [];

    // Aggregate emotion pie data from per-evaluation tone_data if present
    const emotionTotals = {};
    let toneEvalCount = 0;
    questionScores.forEach((ev) => {
        const fa = ev.tone_data?.full_analysis;
        if (!fa) return;
        toneEvalCount++;
        Object.entries(fa).forEach(([emotion, pct]) => {
            const val = parseFloat(pct) || 0;
            emotionTotals[emotion] = (emotionTotals[emotion] || 0) + val;
        });
    });
    const toneData = Object.entries(emotionTotals)
        .map(([emotion, total]) => ({ emotion, value: toneEvalCount > 0 ? total / toneEvalCount : 0 }))
        .sort((a, b) => b.value - a.value)
        .filter(d => d.value > 0.5);

    const hasToneSection = dominantTone || toneData.length > 0 || observations.length > 0;
    const interviewDone  = candidate.interviewStatus === "completed";

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-5xl mx-auto px-6">

                {/* Back */}
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
                    <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
                        <Link to="/hr/jobs">
                            <ArrowLeft className="w-4 h-4 mr-1" />
                            Back to Jobs
                        </Link>
                    </Button>
                </motion.div>

                {/* Profile Header */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
                    className="bg-card rounded-xl border border-border shadow-sm p-6 mb-6">
                    <div className="flex flex-col md:flex-row gap-6 items-start">
                        <div className="w-20 h-20 rounded-full gradient-cobalt flex items-center justify-center text-2xl font-bold text-primary-foreground">
                            {(candidate.name || "C").split(" ").filter(Boolean).map(n => n[0]).join("").toUpperCase()}
                        </div>
                        <div className="flex-1">
                            <div className="flex flex-col md:flex-row md:items-center gap-3 mb-3">
                                <h1 className="text-2xl font-bold text-foreground">{candidate.name}</h1>
                                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${rec.color}`}>{rec.label}</span>
                                {ir.performance_level && <PerformanceBadge level={ir.performance_level} />}
                                {ir.hiring_signal     && <HiringBadge signal={ir.hiring_signal} />}
                            </div>
                            <div className="grid sm:grid-cols-2 gap-3 text-sm text-muted-foreground">
                                {candidate.email && <div className="flex items-center gap-2"><Mail className="w-4 h-4" />{candidate.email}</div>}
                                {candidate.phone && <div className="flex items-center gap-2"><Phone className="w-4 h-4" />{candidate.phone}</div>}
                                <div className="flex items-center gap-2">
                                    <Briefcase className="w-4 h-4" />
                                    {interviewDone ? "Interview Completed" : candidate.interviewStatus || "Not Invited"}
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Score Cards */}
                <div className="grid sm:grid-cols-3 gap-4 mb-6">
                    {[
                        { label: "CV Match Score",    value: candidate.matchScore    || 0, color: "cobalt", sub: null },
                        { label: "Interview Score",   value: candidate.interviewScore|| 0, color: interviewDone ? "mint" : "muted", sub: interviewDone ? null : "Not yet interviewed" },
                        { label: "Total Score",       value: candidate.totalScore    || 0, color: "cobalt", sub: "40% CV + 60% Interview" },
                    ].map(({ label, value, color, sub }, i) => (
                        <motion.div key={i} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.05 }}
                            className="bg-card rounded-xl border border-border shadow-sm p-5 text-center">
                            <p className="text-xs font-medium text-muted-foreground mb-3">{label}</p>
                            <CircularProgress value={Math.round(value)} size={100} strokeWidth={7} color={color} />
                            {sub && <p className="text-[10px] text-muted-foreground mt-2">{sub}</p>}
                        </motion.div>
                    ))}
                </div>

                {/* Skills Analysis */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
                    className="bg-card rounded-xl border border-border shadow-sm mb-6">
                    <SectionHeader icon={Star} label="Skills Analysis" color="text-cobalt" />
                    <div className="p-5 space-y-4">
                        {matched.length > 0 && (
                            <div>
                                <div className="flex items-center gap-2 mb-2"><CheckCircle2 className="w-4 h-4 text-mint" /><span className="text-sm font-medium text-foreground">Matched ({matched.length})</span></div>
                                <div className="flex flex-wrap gap-1.5">{matched.map(s => <span key={s} className="text-xs px-2.5 py-1 rounded-lg bg-mint/10 text-mint-dark border border-mint/20">{s}</span>)}</div>
                            </div>
                        )}
                        {missing.length > 0 && (
                            <div>
                                <div className="flex items-center gap-2 mb-2"><XCircle className="w-4 h-4 text-destructive" /><span className="text-sm font-medium text-foreground">Missing ({missing.length})</span></div>
                                <div className="flex flex-wrap gap-1.5">{missing.map(s => <span key={s} className="text-xs px-2.5 py-1 rounded-lg bg-destructive/10 text-destructive border border-destructive/20">{s}</span>)}</div>
                            </div>
                        )}
                        {extra.length > 0 && (
                            <div>
                                <div className="flex items-center gap-2 mb-2"><Star className="w-4 h-4 text-cobalt" /><span className="text-sm font-medium text-foreground">Bonus ({extra.length})</span></div>
                                <div className="flex flex-wrap gap-1.5">{extra.map(s => <span key={s} className="text-xs px-2.5 py-1 rounded-lg bg-cobalt/10 text-cobalt border border-cobalt/20">{s}</span>)}</div>
                            </div>
                        )}
                        {matched.length === 0 && missing.length === 0 && extra.length === 0 && (
                            <p className="text-sm text-muted-foreground italic">No skill data available.</p>
                        )}
                    </div>
                </motion.div>

                {/* ── Interview Report (only if completed) ── */}
                {!interviewDone && (
                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
                        className="bg-card rounded-xl border border-border shadow-sm p-8 text-center">
                        <Send className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                        <p className="text-sm text-muted-foreground">
                            {candidate.interviewStatus === "invited"
                                ? "Interview invitation sent. Waiting for completion."
                                : "Candidate has not been invited to interview yet."}
                        </p>
                    </motion.div>
                )}

                {interviewDone && (
                    <>
                        {/* Score overview + question score bars */}
                        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
                            className="bg-card rounded-xl border border-border shadow-sm p-8 mb-6">
                            <div className="flex flex-col md:flex-row items-center gap-8">
                                <CircularProgress value={Math.round(avgScore)} size={140} strokeWidth={10}
                                    label="Interview Score" sublabel={scoreLabel} color={scoreColor} />
                                <div className="flex-1 w-full">
                                    {ir.summary && (
                                        <p className="text-sm text-muted-foreground leading-relaxed mb-4 italic">{ir.summary}</p>
                                    )}
                                    {questionScores.length > 0 && (
                                        <>
                                            <h3 className="font-semibold text-foreground mb-4">Question Scores</h3>
                                            <div className="space-y-3">
                                                {questionScores.map((e, idx) => (
                                                    <div key={idx} className="flex items-center gap-3">
                                                        <span className="text-xs text-muted-foreground w-8 shrink-0">Q{idx + 1}</span>
                                                        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                                            <motion.div
                                                                initial={{ width: 0 }}
                                                                animate={{ width: `${e.score}%` }}
                                                                transition={{ delay: 0.35 + idx * 0.07, duration: 0.5 }}
                                                                className={`h-full rounded-full ${e.score >= 80 ? "bg-mint" : e.score >= 60 ? "gradient-cobalt" : "bg-warning"}`}
                                                            />
                                                        </div>
                                                        <span className="text-sm font-semibold text-foreground w-10 text-right">{e.score}%</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </>
                                    )}
                                </div>
                            </div>
                        </motion.div>

                        {/* Detailed Q&A Breakdown */}
                        {questionScores.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-6">
                                <SectionHeader icon={BarChart3} label="Detailed Breakdown" />
                                <div className="divide-y divide-border">
                                    {questionScores.map((e, idx) => (
                                        <motion.div key={idx} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                                            transition={{ delay: 0.4 + idx * 0.04 }} className="p-5">
                                            <div className="flex items-start justify-between gap-4 mb-3">
                                                <div className="flex-1">
                                                    <p className="text-sm font-medium text-foreground mb-1">Q{idx + 1}: {e.question}</p>
                                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                                        <span className="font-medium text-foreground/70">Answer: </span>
                                                        {e.answer || <em className="text-muted-foreground/50">No answer recorded</em>}
                                                    </p>
                                                </div>
                                                <div className="flex flex-col items-end gap-1 shrink-0">
                                                    <div className={`px-3 py-1.5 rounded-lg text-sm font-bold ${e.score >= 80 ? "bg-mint/10 text-mint" : e.score >= 60 ? "bg-cobalt/10 text-cobalt" : "bg-warning/10 text-warning"}`}>
                                                        {e.score}%
                                                    </div>
                                                    {e.classification && (
                                                        <span className="text-[10px] font-medium text-muted-foreground uppercase">{e.classification}</span>
                                                    )}
                                                </div>
                                            </div>
                                            {e.feedback && (
                                                <div className="flex items-start gap-2 mt-2 pl-2 border-l-2 border-cobalt/20">
                                                    <Lightbulb className="w-3.5 h-3.5 text-cobalt mt-0.5 shrink-0" />
                                                    <p className="text-xs text-muted-foreground leading-relaxed">{e.feedback}</p>
                                                </div>
                                            )}
                                            {e.suggested_improvement && (
                                                <div className="flex items-start gap-2 mt-1.5 pl-2 border-l-2 border-mint/20">
                                                    <TrendingUp className="w-3.5 h-3.5 text-mint mt-0.5 shrink-0" />
                                                    <p className="text-xs text-muted-foreground leading-relaxed">{e.suggested_improvement}</p>
                                                </div>
                                            )}
                                        </motion.div>
                                    ))}
                                </div>
                            </motion.div>
                        )}

                        {/* Strengths */}
                        {strengths.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-6">
                                <SectionHeader icon={CheckCircle2} label="Strengths" color="text-mint" />
                                <div className="p-5 space-y-4">
                                    {strengths.map((s, i) => (
                                        <div key={i} className="flex items-start gap-3">
                                            <ThumbsUp className="w-4 h-4 text-mint mt-0.5 shrink-0" />
                                            <div>
                                                {typeof s === "object" ? (
                                                    <>
                                                        <p className="text-sm font-semibold text-foreground">{s.area || s.text}</p>
                                                        {s.evidence && <p className="text-xs text-muted-foreground mt-0.5"><span className="font-medium text-foreground/60">Evidence: </span>{s.evidence}</p>}
                                                        {s.impact   && <p className="text-xs text-mint/80 mt-0.5"><span className="font-medium">Why it matters: </span>{s.impact}</p>}
                                                    </>
                                                ) : (
                                                    <p className="text-sm text-muted-foreground">{s}</p>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}
                        {strengths.length === 0 && fallbackStrengths.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-6">
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

                        {/* Areas to Improve */}
                        {weaknesses.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-6">
                                <SectionHeader icon={AlertCircle} label="Areas to Improve" color="text-warning" />
                                <div className="p-5 space-y-4">
                                    {weaknesses.map((w, i) => (
                                        <div key={i} className="flex items-start gap-3">
                                            <ThumbsDown className="w-4 h-4 text-warning mt-0.5 shrink-0" />
                                            <div>
                                                {typeof w === "object" ? (
                                                    <>
                                                        <p className="text-sm font-semibold text-foreground">{w.area || w.text}</p>
                                                        {w.evidence && <p className="text-xs text-muted-foreground mt-0.5"><span className="font-medium text-foreground/60">Evidence: </span>{w.evidence}</p>}
                                                        {w.impact   && <p className="text-xs text-warning/80 mt-0.5"><span className="font-medium">Impact: </span>{w.impact}</p>}
                                                    </>
                                                ) : (
                                                    <p className="text-sm text-muted-foreground">{w}</p>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}
                        {weaknesses.length === 0 && fallbackImprovements.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-6">
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

                        {/* How to Improve */}
                        {improvements.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.55 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-6">
                                <SectionHeader icon={TrendingUp} label="How to Improve" color="text-cobalt" />
                                <div className="divide-y divide-border">
                                    {improvements.map((imp, i) => (
                                        <div key={i} className="p-5">
                                            {typeof imp === "object" ? (
                                                <>
                                                    <p className="text-sm font-semibold text-foreground mb-3">{imp.weakness_area}</p>
                                                    <div className="space-y-2.5">
                                                        {imp.what_is_wrong   && <div className="flex items-start gap-2.5"><span className="text-xs font-bold text-warning/80 w-10 pt-0.5 shrink-0">WHAT</span><p className="text-xs text-muted-foreground leading-relaxed">{imp.what_is_wrong}</p></div>}
                                                        {imp.why_it_matters  && <div className="flex items-start gap-2.5"><span className="text-xs font-bold text-cobalt/80 w-10 pt-0.5 shrink-0">WHY</span><p className="text-xs text-muted-foreground leading-relaxed">{imp.why_it_matters}</p></div>}
                                                        {imp.how_to_improve  && <div className="flex items-start gap-2.5"><span className="text-xs font-bold text-mint/80 w-10 pt-0.5 shrink-0">HOW</span><p className="text-xs text-muted-foreground leading-relaxed">{imp.how_to_improve}</p></div>}
                                                    </div>
                                                </>
                                            ) : (
                                                <p className="text-sm text-muted-foreground">{safeStr(imp)}</p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}

                        {/* Tips */}
                        {tips.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-6">
                                <SectionHeader icon={Lightbulb} label="Interview Tips" color="text-yellow-500" />
                                <div className="p-5 space-y-3">
                                    {tips.map((t, i) => (
                                        <div key={i} className="flex items-start gap-3">
                                            {typeof t === "object" && t.category
                                                ? <div className="shrink-0 mt-0.5 px-2 py-0.5 rounded text-xs font-semibold bg-yellow-500/10 text-yellow-600 border border-yellow-500/20">{t.category}</div>
                                                : <Lightbulb className="w-4 h-4 text-yellow-500 mt-0.5 shrink-0" />
                                            }
                                            <p className="text-xs text-muted-foreground leading-relaxed">{typeof t === "object" ? (t.tip || safeStr(t)) : t}</p>
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}

                        {/* Recommended Topics */}
                        {recTopics.length > 0 && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.62 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-6">
                                <SectionHeader icon={BookOpen} label="Recommended Study Topics" color="text-cobalt" />
                                <div className="p-5 flex flex-wrap gap-2">
                                    {recTopics.map((topic, i) => (
                                        <span key={i} className="px-3 py-1.5 rounded-full text-xs font-medium bg-cobalt/10 text-cobalt border border-cobalt/20">
                                            {safeStr(topic)}
                                        </span>
                                    ))}
                                </div>
                            </motion.div>
                        )}

                        {/* Communication & Tone */}
                        {hasToneSection && (
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.65 }}
                                className="bg-card rounded-xl border border-border shadow-sm mb-8">
                                <SectionHeader icon={Mic} label="Communication & Tone Analysis" color="text-indigo-500" />
                                <div className="p-5 space-y-6">
                                    <div className="flex flex-wrap gap-3">
                                        {dominantTone && (
                                            <div className="flex flex-col gap-0.5 px-4 py-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20 min-w-[110px]">
                                                <span className="text-[10px] font-semibold text-indigo-500/70 uppercase tracking-wider">Dominant Tone</span>
                                                <span className="text-sm font-bold text-foreground capitalize">{dominantTone}</span>
                                            </div>
                                        )}
                                        {confidenceLevel && (
                                            <div className="flex flex-col gap-0.5 px-4 py-3 rounded-lg bg-muted/50 border border-border min-w-[110px]">
                                                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Confidence</span>
                                                <span className="text-sm font-bold text-foreground capitalize">{confidenceLevel}</span>
                                            </div>
                                        )}
                                        {clarityLevel && (
                                            <div className="flex flex-col gap-0.5 px-4 py-3 rounded-lg bg-muted/50 border border-border min-w-[110px]">
                                                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Clarity</span>
                                                <span className="text-sm font-bold text-foreground capitalize">{clarityLevel}</span>
                                            </div>
                                        )}
                                        {toneEffective && (
                                            <div className="flex flex-col gap-0.5 px-4 py-3 rounded-lg bg-muted/50 border border-border min-w-[110px]">
                                                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Effectiveness</span>
                                                <span className={`text-sm font-bold capitalize ${toneEffective === "effective" ? "text-emerald-500" : "text-amber-500"}`}>{toneEffective}</span>
                                            </div>
                                        )}
                                    </div>

                                    {toneData.length > 0 && (() => {
                                        const chartData = toneData.slice(0, 6).map((d, i) => ({
                                            name: d.emotion.charAt(0).toUpperCase() + d.emotion.slice(1),
                                            value: parseFloat(d.value.toFixed(1)),
                                            color: getToneColor(d.emotion, i),
                                        }));
                                        return (
                                            <div>
                                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Emotion Distribution</p>
                                                <ResponsiveContainer width="100%" height={220}>
                                                    <PieChart>
                                                        <Pie data={chartData} cx="50%" cy="45%" innerRadius={58} outerRadius={85}
                                                            paddingAngle={3} dataKey="value" strokeWidth={0}>
                                                            {chartData.map((entry, i) => <Cell key={i} fill={entry.color} opacity={0.9} />)}
                                                        </Pie>
                                                        <Tooltip content={<ToneTooltip />} />
                                                        <Legend content={<ToneLegend />}
                                                            payload={chartData.map(d => ({ value: d.name, color: d.color }))} />
                                                    </PieChart>
                                                </ResponsiveContainer>
                                            </div>
                                        );
                                    })()}

                                    {observations.length > 0 && (
                                        <div className="space-y-2">
                                            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Key Observations</p>
                                            <ul className="space-y-2">
                                                {observations.map((obs, i) => (
                                                    <li key={i} className="flex items-start gap-2.5 text-xs text-muted-foreground leading-relaxed">
                                                        <span className="shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-indigo-400" />
                                                        {obs}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {recommendations.length > 0 && (
                                        <div className="space-y-2">
                                            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Recommendations</p>
                                            <ul className="space-y-2">
                                                {recommendations.map((rec, i) => (
                                                    <li key={i} className="flex items-start gap-2.5 text-xs text-muted-foreground leading-relaxed">
                                                        <span className="shrink-0 mt-0.5 text-emerald-500 font-bold text-sm leading-none">↗</span>
                                                        {rec}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </>
                )}
            </main>
        </div>
    );
};

export default CandidateProfile;
