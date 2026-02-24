import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import Navbar from "@/components/Navbar";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import { CheckCircle2, AlertCircle, TrendingUp, ArrowLeft, Download, Lightbulb, ThumbsUp, ThumbsDown, BarChart3 } from "lucide-react";

const strengths = [
    { title: "Technical Knowledge", description: "Demonstrated strong understanding of React architecture, state management patterns, and performance optimization techniques." },
    { title: "Communication Clarity", description: "Responses were well-structured, using the STAR method effectively to illustrate past experiences." },
    { title: "Problem Solving", description: "Showed systematic approach to breaking down complex problems into manageable components." },
];

const weaknesses = [
    { title: "System Design Depth", description: "Could elaborate more on trade-offs when discussing database choices and caching strategies." },
    { title: "Behavioral Examples", description: "Some answers lacked specific metrics or outcomes. Quantify achievements where possible." },
];

const suggestions = [
    "Practice explaining system design decisions with specific trade-off analysis",
    "Prepare 3-5 STAR stories with quantified outcomes for behavioral questions",
    "Study distributed systems concepts, especially consistency vs availability",
    "Work on concise responses — aim for 2 minute answers max",
];

const FeedbackReport = () => {
    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-5xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8 flex items-center justify-between"
                >
                    <div>
                        <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
                            <Link to="/candidate">
                                <ArrowLeft className="w-4 h-4 mr-1" />
                                Back to Dashboard
                            </Link>
                        </Button>
                        <h1 className="text-2xl font-bold text-foreground">AI Feedback Report</h1>
                        <p className="text-muted-foreground mt-1">Senior Frontend Developer — Feb 5, 2026</p>
                    </div>
                    <Button variant="outline" size="sm">
                        <Download className="w-4 h-4 mr-1.5" />
                        Export PDF
                    </Button>
                </motion.div>

                {/* Score Overview */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="bg-card rounded-xl border border-border shadow-sm p-8 mb-6"
                >
                    <div className="flex flex-col md:flex-row items-center gap-8">
                        <CircularProgress value={88} size={140} strokeWidth={10} label="Overall Score" sublabel="Excellent" color="mint" />
                        <div className="flex-1 grid sm:grid-cols-3 gap-6">
                            <div className="text-center sm:text-left">
                                <div className="flex items-center gap-2 justify-center sm:justify-start mb-1">
                                    <BarChart3 className="w-4 h-4 text-cobalt" />
                                    <span className="text-sm text-muted-foreground">Technical</span>
                                </div>
                                <p className="text-2xl font-bold text-foreground">92%</p>
                                <div className="w-full h-1.5 bg-muted rounded-full mt-2">
                                    <div className="h-full gradient-cobalt rounded-full" style={{ width: "92%" }} />
                                </div>
                            </div>
                            <div className="text-center sm:text-left">
                                <div className="flex items-center gap-2 justify-center sm:justify-start mb-1">
                                    <TrendingUp className="w-4 h-4 text-mint" />
                                    <span className="text-sm text-muted-foreground">Communication</span>
                                </div>
                                <p className="text-2xl font-bold text-foreground">85%</p>
                                <div className="w-full h-1.5 bg-muted rounded-full mt-2">
                                    <div className="h-full gradient-mint rounded-full" style={{ width: "85%" }} />
                                </div>
                            </div>
                            <div className="text-center sm:text-left">
                                <div className="flex items-center gap-2 justify-center sm:justify-start mb-1">
                                    <ThumbsUp className="w-4 h-4 text-warning" />
                                    <span className="text-sm text-muted-foreground">Confidence</span>
                                </div>
                                <p className="text-2xl font-bold text-foreground">87%</p>
                                <div className="w-full h-1.5 bg-muted rounded-full mt-2">
                                    <div className="h-full bg-warning rounded-full" style={{ width: "87%" }} />
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>

                <div className="grid md:grid-cols-2 gap-6 mb-6">
                    {/* Strengths */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="bg-card rounded-xl border border-border shadow-sm"
                    >
                        <div className="p-5 border-b border-border flex items-center gap-2">
                            <CheckCircle2 className="w-5 h-5 text-mint" />
                            <h3 className="font-semibold text-foreground">Strengths</h3>
                        </div>
                        <div className="p-5 space-y-4">
                            {strengths.map((s, i) => (
                                <motion.div
                                    key={s.title}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.3 + i * 0.08 }}
                                >
                                    <div className="flex items-start gap-3">
                                        <div className="w-6 h-6 rounded-full bg-mint/10 flex items-center justify-center mt-0.5 shrink-0">
                                            <ThumbsUp className="w-3 h-3 text-mint" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-foreground">{s.title}</p>
                                            <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">{s.description}</p>
                                        </div>
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    </motion.div>

                    {/* Weaknesses */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.25 }}
                        className="bg-card rounded-xl border border-border shadow-sm"
                    >
                        <div className="p-5 border-b border-border flex items-center gap-2">
                            <AlertCircle className="w-5 h-5 text-warning" />
                            <h3 className="font-semibold text-foreground">Areas for Improvement</h3>
                        </div>
                        <div className="p-5 space-y-4">
                            {weaknesses.map((w, i) => (
                                <motion.div
                                    key={w.title}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.35 + i * 0.08 }}
                                >
                                    <div className="flex items-start gap-3">
                                        <div className="w-6 h-6 rounded-full bg-warning/10 flex items-center justify-center mt-0.5 shrink-0">
                                            <ThumbsDown className="w-3 h-3 text-warning" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-foreground">{w.title}</p>
                                            <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">{w.description}</p>
                                        </div>
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    </motion.div>
                </div>

                {/* Suggested Improvements */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.35 }}
                    className="bg-card rounded-xl border border-border shadow-sm"
                >
                    <div className="p-5 border-b border-border flex items-center gap-2">
                        <Lightbulb className="w-5 h-5 text-cobalt" />
                        <h3 className="font-semibold text-foreground">Suggested Improvements</h3>
                    </div>
                    <div className="p-5">
                        <ul className="space-y-3">
                            {suggestions.map((s, i) => (
                                <motion.li
                                    key={i}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.4 + i * 0.06 }}
                                    className="flex items-start gap-3"
                                >
                                    <span className="w-6 h-6 rounded-full bg-cobalt/10 flex items-center justify-center text-xs font-semibold text-cobalt shrink-0">
                                        {i + 1}
                                    </span>
                                    <p className="text-sm text-muted-foreground leading-relaxed">{s}</p>
                                </motion.li>
                            ))}
                        </ul>
                    </div>
                </motion.div>
            </main>
        </div>
    );
};

export default FeedbackReport;
