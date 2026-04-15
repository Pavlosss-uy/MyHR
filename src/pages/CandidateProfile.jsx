import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Navbar from "@/components/Navbar";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import { getCandidate } from "@/lib/interviewApi";
import {
    ArrowLeft,
    Mail,
    Phone,
    Briefcase,
    Star,
    Download,
    CheckCircle2,
    AlertCircle,
    Loader2,
    Brain,
    XCircle,
    Mic,
    BarChart3,
    Send,
} from "lucide-react";

const statusColors = {
    Recommended: "bg-mint-light text-mint-dark",
    "Under Review": "bg-warning/10 text-warning",
    "Needs Improvement": "bg-destructive/10 text-destructive",
};

const getRecommendation = (score) => {
    if (score >= 85) return { label: "Strong Hire", color: "bg-mint/10 text-mint-dark border-mint/20" };
    if (score >= 70) return { label: "Hire", color: "bg-cobalt/10 text-cobalt border-cobalt/20" };
    if (score >= 55) return { label: "Consider", color: "bg-warning/10 text-warning border-warning/20" };
    return { label: "No Hire", color: "bg-destructive/10 text-destructive border-destructive/20" };
};

const CandidateProfile = () => {
    const { id } = useParams();
    const [searchParams] = useSearchParams();
    const jobId = searchParams.get("jobId") || "";

    const [candidate, setCandidate] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        if (!jobId || !id) {
            setError("Missing job or candidate reference.");
            setLoading(false);
            return;
        }

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

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
            </div>
        );
    }

    if (error || !candidate) {
        return (
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
    }

    const rec = getRecommendation(candidate.totalScore || candidate.matchScore || 0);
    const matched = candidate.matchDetails?.matched || [];
    const missing = candidate.matchDetails?.missing || [];
    const extra = candidate.matchDetails?.extra || [];
    const report = candidate.interviewReport || {};

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-5xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-6"
                >
                    <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
                        <Link to="/hr/jobs">
                            <ArrowLeft className="w-4 h-4 mr-1" />
                            Back to Jobs
                        </Link>
                    </Button>
                </motion.div>

                {/* Profile Header */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="bg-card rounded-xl border border-border shadow-sm p-6 mb-6"
                >
                    <div className="flex flex-col md:flex-row gap-6 items-start">
                        <div className="w-20 h-20 rounded-full gradient-cobalt flex items-center justify-center text-2xl font-bold text-primary-foreground">
                            {(candidate.name || "C").split(" ").map(n => n[0]).join("").toUpperCase()}
                        </div>
                        <div className="flex-1">
                            <div className="flex flex-col md:flex-row md:items-center gap-3 mb-3">
                                <h1 className="text-2xl font-bold text-foreground">{candidate.name}</h1>
                                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${rec.color}`}>
                                    {rec.label}
                                </span>
                            </div>
                            <div className="grid sm:grid-cols-2 gap-3 text-sm text-muted-foreground">
                                {candidate.email && (
                                    <div className="flex items-center gap-2">
                                        <Mail className="w-4 h-4" />
                                        {candidate.email}
                                    </div>
                                )}
                                {candidate.phone && (
                                    <div className="flex items-center gap-2">
                                        <Phone className="w-4 h-4" />
                                        {candidate.phone}
                                    </div>
                                )}
                                <div className="flex items-center gap-2">
                                    <Briefcase className="w-4 h-4" />
                                    {candidate.interviewStatus === "completed" ? "Interview Completed" : candidate.interviewStatus || "Not Invited"}
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>

                {/* Score Cards */}
                <div className="grid sm:grid-cols-3 gap-4 mb-6">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.15 }}
                        className="bg-card rounded-xl border border-border shadow-sm p-5 text-center"
                    >
                        <p className="text-xs font-medium text-muted-foreground mb-3">CV Match Score</p>
                        <CircularProgress value={Math.round(candidate.matchScore || 0)} size={100} strokeWidth={7} color="cobalt" />
                    </motion.div>
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="bg-card rounded-xl border border-border shadow-sm p-5 text-center"
                    >
                        <p className="text-xs font-medium text-muted-foreground mb-3">Interview Score</p>
                        <CircularProgress
                            value={Math.round(candidate.interviewScore || 0)}
                            size={100}
                            strokeWidth={7}
                            color={candidate.interviewStatus === "completed" ? "mint" : "muted"}
                        />
                        {candidate.interviewStatus !== "completed" && (
                            <p className="text-[10px] text-muted-foreground mt-2">Not yet interviewed</p>
                        )}
                    </motion.div>
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.25 }}
                        className="bg-card rounded-xl border border-border shadow-sm p-5 text-center"
                    >
                        <p className="text-xs font-medium text-muted-foreground mb-3">Total Score</p>
                        <CircularProgress
                            value={Math.round(candidate.totalScore || candidate.matchScore || 0)}
                            size={100}
                            strokeWidth={7}
                            color="cobalt"
                        />
                        <p className="text-[10px] text-muted-foreground mt-2">40% CV + 60% Interview</p>
                    </motion.div>
                </div>

                <div className="grid lg:grid-cols-2 gap-6">
                    {/* Skills Match */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="bg-card rounded-xl border border-border shadow-sm"
                    >
                        <div className="p-5 border-b border-border">
                            <h3 className="font-semibold text-foreground">Skills Analysis</h3>
                        </div>
                        <div className="p-5 space-y-4">
                            {/* Matched */}
                            {matched.length > 0 && (
                                <div>
                                    <div className="flex items-center gap-2 mb-2">
                                        <CheckCircle2 className="w-4 h-4 text-mint" />
                                        <span className="text-sm font-medium text-foreground">Matched ({matched.length})</span>
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {matched.map((s) => (
                                            <span key={s} className="text-xs px-2.5 py-1 rounded-lg bg-mint/10 text-mint-dark border border-mint/20">
                                                {s}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Missing */}
                            {missing.length > 0 && (
                                <div>
                                    <div className="flex items-center gap-2 mb-2">
                                        <XCircle className="w-4 h-4 text-destructive" />
                                        <span className="text-sm font-medium text-foreground">Missing ({missing.length})</span>
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {missing.map((s) => (
                                            <span key={s} className="text-xs px-2.5 py-1 rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
                                                {s}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Extra */}
                            {extra.length > 0 && (
                                <div>
                                    <div className="flex items-center gap-2 mb-2">
                                        <Star className="w-4 h-4 text-cobalt-light" />
                                        <span className="text-sm font-medium text-foreground">Bonus ({extra.length})</span>
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {extra.map((s) => (
                                            <span key={s} className="text-xs px-2.5 py-1 rounded-lg bg-cobalt/10 text-cobalt border border-cobalt/20">
                                                {s}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </motion.div>

                    {/* Interview Report */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.35 }}
                        className="bg-card rounded-xl border border-border shadow-sm"
                    >
                        <div className="p-5 border-b border-border flex items-center gap-2">
                            <Brain className="w-4 h-4 text-cobalt" />
                            <h3 className="font-semibold text-foreground">Interview Report</h3>
                        </div>
                        <div className="p-5 space-y-4">
                            {candidate.interviewStatus !== "completed" ? (
                                <div className="text-center py-6">
                                    <Send className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                                    <p className="text-sm text-muted-foreground">
                                        {candidate.interviewStatus === "invited"
                                            ? "Interview invitation sent. Waiting for completion."
                                            : "Candidate has not been invited to interview yet."}
                                    </p>
                                </div>
                            ) : (
                                <>
                                    {report.summary && (
                                        <p className="text-sm text-muted-foreground leading-relaxed">{report.summary}</p>
                                    )}

                                    {report.strengths?.length > 0 && (
                                        <div>
                                            <p className="text-xs font-medium text-foreground mb-1.5 flex items-center gap-1">
                                                <CheckCircle2 className="w-3 h-3 text-mint" /> Strengths
                                            </p>
                                            <ul className="space-y-1">
                                                {report.strengths.map((s, i) => (
                                                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                                        <span className="w-1 h-1 rounded-full bg-mint mt-2 shrink-0" />
                                                        {s}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {report.weaknesses?.length > 0 && (
                                        <div>
                                            <p className="text-xs font-medium text-foreground mb-1.5 flex items-center gap-1">
                                                <AlertCircle className="w-3 h-3 text-warning" /> Areas to Improve
                                            </p>
                                            <ul className="space-y-1">
                                                {report.weaknesses.map((w, i) => (
                                                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                                        <span className="w-1 h-1 rounded-full bg-warning mt-2 shrink-0" />
                                                        {w}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {report.communication && (
                                        <div className="flex items-center gap-4 pt-2 border-t border-border">
                                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                                <Mic className="w-3 h-3" />
                                                Tone: <span className="text-foreground font-medium capitalize">{report.communication.tone}</span>
                                            </div>
                                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                                <BarChart3 className="w-3 h-3" />
                                                Confidence: <span className="text-foreground font-medium capitalize">{report.communication.confidence}</span>
                                            </div>
                                        </div>
                                    )}

                                    {!report.summary && !report.strengths && (
                                        <p className="text-sm text-muted-foreground italic">Interview completed. Detailed report data is available.</p>
                                    )}
                                </>
                            )}
                        </div>
                    </motion.div>
                </div>
            </main>
        </div>
    );
};

export default CandidateProfile;
