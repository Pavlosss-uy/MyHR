import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import CircularProgress from "@/components/CircularProgress";
import {
    X,
    CheckCircle2,
    XCircle,
    AlertCircle,
    Send,
    FileText,
    Brain,
    Star,
    Mic,
    BarChart3,
} from "lucide-react";

const MatchAnalysisDrawer = ({ candidate, jobTitle, isOpen, onClose, onInvite }) => {
    if (!candidate) return null;

    const { name, email, matchScore, matchDetails, cvSkills, interviewStatus, interviewScore, totalScore, interviewReport } = candidate;
    const matched = matchDetails?.matched || [];
    const missing = matchDetails?.missing || [];
    const extra = matchDetails?.extra || [];

    const scoreColor = matchScore >= 75 ? "mint" : matchScore >= 50 ? "cobalt" : "destructive";

    // Determine recommendation level
    const getRecommendation = () => {
        const score = totalScore || matchScore;
        if (score >= 85) return { label: "Strong Hire", color: "text-mint-dark bg-mint/10 border-mint/20" };
        if (score >= 70) return { label: "Hire", color: "text-cobalt bg-cobalt/10 border-cobalt/20" };
        if (score >= 55) return { label: "Consider", color: "text-warning bg-warning/10 border-warning/20" };
        return { label: "No Hire", color: "text-destructive bg-destructive/10 border-destructive/20" };
    };

    const rec = getRecommendation();

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
                        onClick={onClose}
                    />

                    {/* Drawer */}
                    <motion.div
                        initial={{ x: "100%" }}
                        animate={{ x: 0 }}
                        exit={{ x: "100%" }}
                        transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-lg bg-card border-l border-border shadow-xl overflow-y-auto"
                    >
                        {/* Header */}
                        <div className="sticky top-0 bg-card/95 backdrop-blur-sm z-10 border-b border-border px-6 py-4 flex items-center justify-between">
                            <div>
                                <h2 className="font-bold text-foreground text-lg">{name}</h2>
                                <p className="text-sm text-muted-foreground">{jobTitle || "Position"}</p>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-2 rounded-lg hover:bg-muted transition-colors"
                            >
                                <X className="w-5 h-5 text-muted-foreground" />
                            </button>
                        </div>

                        <div className="px-6 py-6 space-y-6">
                            {/* Score overview */}
                            <div className="flex items-center gap-6">
                                <CircularProgress value={Math.round(matchScore)} size={100} strokeWidth={7} color={scoreColor} />
                                <div className="space-y-2">
                                    <span className={`inline-flex text-xs font-semibold px-2.5 py-1 rounded-full border ${rec.color}`}>
                                        {rec.label}
                                    </span>
                                    <p className="text-sm text-muted-foreground">CV Match Score</p>
                                    {interviewStatus === "completed" && (
                                        <div className="space-y-1">
                                            <p className="text-sm text-muted-foreground">
                                                Interview: <span className="font-semibold text-foreground">{Math.round(interviewScore)}%</span>
                                            </p>
                                            <p className="text-sm text-muted-foreground">
                                                Total: <span className="font-bold text-foreground">{Math.round(totalScore)}%</span>
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Contact */}
                            {email && (
                                <div className="text-sm text-muted-foreground">
                                    📧 {email}
                                </div>
                            )}

                            {/* Matched Skills */}
                            <div>
                                <div className="flex items-center gap-2 mb-3">
                                    <CheckCircle2 className="w-4 h-4 text-mint" />
                                    <h3 className="text-sm font-semibold text-foreground">
                                        Matched Skills ({matched.length})
                                    </h3>
                                </div>
                                {matched.length > 0 ? (
                                    <div className="flex flex-wrap gap-2">
                                        {matched.map((skill) => (
                                            <span
                                                key={skill}
                                                className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-mint/10 text-mint-dark border border-mint/20"
                                            >
                                                <CheckCircle2 className="w-3 h-3" />
                                                {skill}
                                            </span>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground italic">No matching skills found.</p>
                                )}
                            </div>

                            {/* Missing Skills */}
                            <div>
                                <div className="flex items-center gap-2 mb-3">
                                    <XCircle className="w-4 h-4 text-destructive" />
                                    <h3 className="text-sm font-semibold text-foreground">
                                        Missing Skills ({missing.length})
                                    </h3>
                                </div>
                                {missing.length > 0 ? (
                                    <div className="flex flex-wrap gap-2">
                                        {missing.map((skill) => (
                                            <span
                                                key={skill}
                                                className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-destructive/10 text-destructive border border-destructive/20"
                                            >
                                                <XCircle className="w-3 h-3" />
                                                {skill}
                                            </span>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-mint-dark italic">Candidate has all required skills! ✨</p>
                                )}
                            </div>

                            {/* Extra Skills */}
                            {extra.length > 0 && (
                                <div>
                                    <div className="flex items-center gap-2 mb-3">
                                        <Star className="w-4 h-4 text-cobalt-light" />
                                        <h3 className="text-sm font-semibold text-foreground">
                                            Bonus Skills ({extra.length})
                                        </h3>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {extra.map((skill) => (
                                            <span
                                                key={skill}
                                                className="text-sm px-3 py-1.5 rounded-lg bg-cobalt/10 text-cobalt border border-cobalt/20"
                                            >
                                                {skill}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Interview Report (if completed) */}
                            {interviewStatus === "completed" && interviewReport && Object.keys(interviewReport).length > 0 && (
                                <div className="space-y-3">
                                    <div className="flex items-center gap-2">
                                        <Brain className="w-4 h-4 text-cobalt" />
                                        <h3 className="text-sm font-semibold text-foreground">Interview Report</h3>
                                    </div>

                                    {interviewReport.summary && (
                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                            {interviewReport.summary}
                                        </p>
                                    )}

                                    {interviewReport.strengths?.length > 0 && (
                                        <div>
                                            <p className="text-xs font-medium text-foreground mb-1.5 flex items-center gap-1">
                                                <CheckCircle2 className="w-3 h-3 text-mint" /> Strengths
                                            </p>
                                            <ul className="space-y-1">
                                                {interviewReport.strengths.map((s, i) => (
                                                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                                        <span className="w-1 h-1 rounded-full bg-mint mt-2 shrink-0" />
                                                        {typeof s === "string" ? s : (s?.text || s?.description || JSON.stringify(s))}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {interviewReport.weaknesses?.length > 0 && (
                                        <div>
                                            <p className="text-xs font-medium text-foreground mb-1.5 flex items-center gap-1">
                                                <AlertCircle className="w-3 h-3 text-warning" /> Areas to Improve
                                            </p>
                                            <ul className="space-y-1">
                                                {interviewReport.weaknesses.map((w, i) => (
                                                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                                        <span className="w-1 h-1 rounded-full bg-warning mt-2 shrink-0" />
                                                        {typeof w === "string" ? w : (w?.text || w?.description || JSON.stringify(w))}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {interviewReport.communication && (
                                        <div className="flex items-center gap-4 pt-2">
                                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                                <Mic className="w-3 h-3" />
                                                Tone: <span className="text-foreground font-medium capitalize">{interviewReport.communication.tone}</span>
                                            </div>
                                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                                <BarChart3 className="w-3 h-3" />
                                                Confidence: <span className="text-foreground font-medium capitalize">{interviewReport.communication.confidence}</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Actions */}
                            <div className="pt-2 border-t border-border">
                                {interviewStatus === "not_invited" && (
                                    <Button
                                        variant="hero"
                                        className="w-full h-11"
                                        onClick={() => {
                                            onInvite?.(candidate);
                                            onClose();
                                        }}
                                    >
                                        <Send className="w-4 h-4 mr-2" />
                                        Invite to AI Interview
                                    </Button>
                                )}
                                {interviewStatus === "invited" && (
                                    <Button variant="outline" className="w-full h-11" disabled>
                                        <Send className="w-4 h-4 mr-2" />
                                        Interview Invitation Sent
                                    </Button>
                                )}
                            </div>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};

export default MatchAnalysisDrawer;
