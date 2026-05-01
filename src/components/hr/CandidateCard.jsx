import { motion } from "framer-motion";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import { Mail, CheckCircle2, XCircle, ArrowRight, Send, Eye, Loader2, Trash2 } from "lucide-react";

const statusBadge = {
    not_invited: { label: "Not Invited", style: "bg-muted text-muted-foreground" },
    invited: { label: "Invited", style: "bg-warning/10 text-warning" },
    completed: { label: "Completed", style: "bg-mint/10 text-mint-dark" },
};

const CandidateCard = ({ candidate, index = 0, inviting = false, ignoring = false, onViewDetails, onViewReport, onInvite, onIgnore }) => {
    const { name, email, matchScore, matchDetails, interviewStatus, totalScore } = candidate;
    const badge = statusBadge[interviewStatus] || statusBadge.not_invited;
    const matched = matchDetails?.matched || [];
    const missing = matchDetails?.missing || [];

    const scoreColor = matchScore >= 75 ? "mint" : matchScore >= 50 ? "cobalt" : "destructive";

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04, duration: 0.35 }}
            className="group bg-card rounded-xl border border-border p-5 hover:border-cobalt-lighter/30 hover:shadow-cobalt transition-all duration-200"
        >
            <div className="flex items-start gap-4">
                {/* Score */}
                <div className="shrink-0">
                    <CircularProgress value={Math.round(matchScore)} size={64} strokeWidth={5} color={scoreColor} />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-foreground truncate">{name}</h3>
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0 ${badge.style}`}>
                            {badge.label}
                        </span>
                    </div>

                    {email && (
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-3">
                            <Mail className="w-3 h-3" />
                            <span className="truncate">{email}</span>
                        </div>
                    )}

                    {/* Matched skills */}
                    {matched.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-2">
                            {matched.slice(0, 4).map((skill) => (
                                <span
                                    key={skill}
                                    className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-mint/10 text-mint-dark border border-mint/20"
                                >
                                    <CheckCircle2 className="w-2.5 h-2.5" />
                                    {skill}
                                </span>
                            ))}
                            {matched.length > 4 && (
                                <span className="text-[11px] text-muted-foreground px-1">+{matched.length - 4}</span>
                            )}
                        </div>
                    )}

                    {/* Missing skills */}
                    {missing.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-3">
                            {missing.slice(0, 3).map((skill) => (
                                <span
                                    key={skill}
                                    className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-destructive/10 text-destructive border border-destructive/20"
                                >
                                    <XCircle className="w-2.5 h-2.5" />
                                    {skill}
                                </span>
                            ))}
                            {missing.length > 3 && (
                                <span className="text-[11px] text-muted-foreground px-1">+{missing.length - 3}</span>
                            )}
                        </div>
                    )}

                    {/* Total score (if interviewed) */}
                    {interviewStatus === "completed" && totalScore > 0 && (
                        <div className="text-xs text-muted-foreground mb-3">
                            Total Score: <span className="font-semibold text-foreground">{Math.round(totalScore)}%</span>
                            <span className="text-[10px] ml-1">(40% CV + 60% Interview)</span>
                        </div>
                    )}
                </div>

                {/* Ignore button — subtle, appears on card hover */}
                <button
                    onClick={() => onIgnore?.(candidate)}
                    disabled={ignoring}
                    title="Remove candidate"
                    className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                >
                    {ignoring
                        ? <Loader2 className="w-4 h-4 animate-spin" />
                        : <Trash2 className="w-4 h-4" />
                    }
                </button>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
                <Button variant="outline" size="sm" className="flex-1" onClick={() => onViewDetails?.(candidate)}>
                    <Eye className="w-3.5 h-3.5 mr-1" />
                    View Details
                </Button>
                {interviewStatus === "not_invited" && (
                    <Button variant="hero" size="sm" className="flex-1" onClick={() => onInvite?.(candidate)} disabled={inviting}>
                        {inviting
                            ? <><Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />Sending…</>
                            : <><Send className="w-3.5 h-3.5 mr-1" />Invite to Interview</>
                        }
                    </Button>
                )}
                {interviewStatus === "invited" && (
                    <Button variant="outline" size="sm" className="flex-1" disabled>
                        <Send className="w-3.5 h-3.5 mr-1" />
                        Invitation Sent
                    </Button>
                )}
                {interviewStatus === "completed" && (
                    <Button variant="outline" size="sm" className="flex-1" onClick={() => onViewReport?.(candidate)}>
                        <ArrowRight className="w-3.5 h-3.5 mr-1" />
                        View Report
                    </Button>
                )}
            </div>
        </motion.div>
    );
};

export default CandidateCard;
