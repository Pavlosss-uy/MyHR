import { useState } from "react";
import { motion } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import Navbar from "@/components/Navbar";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import { Mic, Clock, TrendingUp, Trophy, ArrowRight, Play, Star, Upload, FileText, X, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { startInterview } from "@/lib/interviewApi";

const pastInterviews = [
    { id: 1, role: "Senior Frontend Developer", company: "TechCorp", date: "Feb 5, 2026", score: 88, duration: "22 min" },
    { id: 2, role: "Full Stack Engineer", company: "StartupXYZ", date: "Feb 3, 2026", score: 76, duration: "18 min" },
    { id: 3, role: "React Developer", company: "InnovateCo", date: "Jan 30, 2026", score: 92, duration: "25 min" },
    { id: 4, role: "Product Manager", company: "BigCorp", date: "Jan 28, 2026", score: 71, duration: "20 min" },
];

const CandidateHome = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const displayName = user?.name || "there";

    // Setup modal state
    const [showSetup, setShowSetup] = useState(false);
    const [cvFile, setCvFile] = useState(null);
    const [jdText, setJdText] = useState("");
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
            // Navigate to interview room with session data
            navigate("/interview", {
                state: {
                    session_id: data.session_id,
                    question: data.question,
                    audio_url: data.audio_url,
                },
            });
        } catch (err) {
            setSetupError(err.message || "Failed to start interview. Make sure the backend is running.");
            setIsStarting(false);
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-6xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <h1 className="text-2xl font-bold text-foreground">Welcome back, {displayName} 👋</h1>
                    <p className="text-muted-foreground mt-1">Track your progress and practice for your next interview.</p>
                </motion.div>

                <div className="grid lg:grid-cols-3 gap-6">
                    {/* Left Column */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Quick Actions */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.1 }}
                            className="gradient-cobalt rounded-2xl p-8 shadow-cobalt-lg"
                        >
                            <h2 className="text-xl font-bold text-primary-foreground mb-2">Ready for your next practice?</h2>
                            <p className="text-cobalt-lighter mb-6">Jump into an AI-powered mock interview and improve your skills.</p>
                            <div className="flex gap-3">
                                <Button
                                    size="lg"
                                    className="bg-card text-primary hover:bg-card/90 shadow-lg"
                                    onClick={() => setShowSetup(true)}
                                >
                                    <Mic className="w-4 h-4 mr-2" />
                                    Start Mock Interview
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="lg"
                                    className="text-primary-foreground border border-primary-foreground/20 hover:bg-primary-foreground/10"
                                    asChild
                                >
                                    <Link to="/feedback">View Last Report</Link>
                                </Button>
                            </div>
                        </motion.div>

                        {/* Stats Grid */}
                        <div className="grid sm:grid-cols-3 gap-4">
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.15 }}
                                className="bg-card rounded-xl border border-border p-5"
                            >
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-9 h-9 rounded-lg bg-cobalt/10 flex items-center justify-center">
                                        <Mic className="w-4 h-4 text-cobalt" />
                                    </div>
                                    <span className="text-sm text-muted-foreground">Total Interviews</span>
                                </div>
                                <p className="text-2xl font-bold text-foreground">12</p>
                            </motion.div>

                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.2 }}
                                className="bg-card rounded-xl border border-border p-5"
                            >
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-9 h-9 rounded-lg bg-mint/10 flex items-center justify-center">
                                        <TrendingUp className="w-4 h-4 text-mint" />
                                    </div>
                                    <span className="text-sm text-muted-foreground">Avg. Score</span>
                                </div>
                                <p className="text-2xl font-bold text-foreground">82%</p>
                            </motion.div>

                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.25 }}
                                className="bg-card rounded-xl border border-border p-5"
                            >
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-9 h-9 rounded-lg bg-warning/10 flex items-center justify-center">
                                        <Clock className="w-4 h-4 text-warning" />
                                    </div>
                                    <span className="text-sm text-muted-foreground">Practice Time</span>
                                </div>
                                <p className="text-2xl font-bold text-foreground">4.2h</p>
                            </motion.div>
                        </div>

                        {/* Past Interviews */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            className="bg-card rounded-xl border border-border shadow-sm"
                        >
                            <div className="p-5 border-b border-border flex items-center justify-between">
                                <h3 className="font-semibold text-foreground">Past Mock Interviews</h3>
                                <Button variant="ghost" size="sm" asChild>
                                    <Link to="/candidate/history">View All</Link>
                                </Button>
                            </div>
                            <div className="divide-y divide-border">
                                {pastInterviews.map((interview) => (
                                    <div key={interview.id} className="px-5 py-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 rounded-lg bg-primary/5 flex items-center justify-center">
                                                <Play className="w-4 h-4 text-primary" />
                                            </div>
                                            <div>
                                                <p className="text-sm font-medium text-foreground">{interview.role}</p>
                                                <p className="text-xs text-muted-foreground">{interview.company} · {interview.date}</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-4">
                                            <div className="text-right">
                                                <div className="flex items-center gap-1">
                                                    <Star className="w-3.5 h-3.5 text-warning fill-warning" />
                                                    <span className="text-sm font-semibold text-foreground">{interview.score}%</span>
                                                </div>
                                                <p className="text-xs text-muted-foreground">{interview.duration}</p>
                                            </div>
                                            <Button variant="ghost" size="sm" asChild>
                                                <Link to="/feedback">
                                                    <ArrowRight className="w-4 h-4" />
                                                </Link>
                                            </Button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    </div>

                    {/* Right Column - Readiness Score */}
                    <div className="space-y-6">
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.2 }}
                            className="bg-card rounded-xl border border-border shadow-sm p-6 text-center"
                        >
                            <h3 className="font-semibold text-foreground mb-6">Interview Readiness</h3>
                            <CircularProgress value={78} size={160} strokeWidth={10} color="cobalt" />
                            <p className="text-sm text-muted-foreground mt-4">Your readiness score is based on recent performance and practice frequency.</p>
                            <Button variant="hero" size="sm" className="mt-4 w-full" onClick={() => setShowSetup(true)}>
                                Improve Score
                            </Button>
                        </motion.div>

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
                                    { label: "First Interview", done: true },
                                    { label: "Score 80+", done: true },
                                    { label: "5 Interviews", done: true },
                                    { label: "Score 95+", done: false },
                                    { label: "10 Day Streak", done: false },
                                ].map((a) => (
                                    <div key={a.label} className="flex items-center gap-3">
                                        <div className={`w-6 h-6 rounded-full flex items-center justify-center ${a.done ? "bg-mint/20" : "bg-muted"}`}>
                                            {a.done ? (
                                                <Trophy className="w-3 h-3 text-mint" />
                                            ) : (
                                                <div className="w-2 h-2 rounded-full bg-muted-foreground/30" />
                                            )}
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

            {/* ─── Interview Setup Modal ─── */}
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
                                onClick={() => { setShowSetup(false); setSetupError(""); }}
                                className="w-8 h-8 rounded-full flex items-center justify-center text-muted-foreground hover:bg-muted transition-colors"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* CV Upload */}
                        <div className="mb-5">
                            <label className="block text-sm font-medium text-foreground mb-2">
                                Upload CV (PDF)
                            </label>
                            <label className="flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-dashed border-border hover:border-cobalt/40 cursor-pointer transition-colors bg-muted/30">
                                <Upload className="w-5 h-5 text-muted-foreground" />
                                <span className="text-sm text-muted-foreground">
                                    {cvFile ? cvFile.name : "Click to choose a PDF file"}
                                </span>
                                <input
                                    type="file"
                                    accept=".pdf"
                                    className="hidden"
                                    onChange={(e) => setCvFile(e.target.files[0] || null)}
                                />
                            </label>
                            {cvFile && (
                                <div className="flex items-center gap-2 mt-2 text-xs text-mint">
                                    <FileText className="w-3.5 h-3.5" />
                                    {cvFile.name} ({Math.round(cvFile.size / 1024)} KB)
                                </div>
                            )}
                        </div>

                        {/* Job Description */}
                        <div className="mb-6">
                            <label className="block text-sm font-medium text-foreground mb-2">
                                Job Description
                            </label>
                            <textarea
                                value={jdText}
                                onChange={(e) => setJdText(e.target.value)}
                                placeholder="Paste the job description here..."
                                rows={5}
                                className="w-full px-4 py-3 rounded-xl border border-border bg-muted/30 text-foreground text-sm placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-cobalt/40 focus:border-cobalt/40 resize-none"
                            />
                        </div>

                        {/* Error */}
                        {setupError && (
                            <p className="text-sm text-destructive mb-4">{setupError}</p>
                        )}

                        {/* Actions */}
                        <div className="flex gap-3">
                            <Button
                                variant="hero"
                                size="lg"
                                className="flex-1"
                                onClick={handleStartInterview}
                                disabled={isStarting}
                            >
                                {isStarting ? (
                                    <>
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                        Initializing AI Agent...
                                    </>
                                ) : (
                                    <>
                                        <Mic className="w-4 h-4 mr-2" />
                                        Start Interview
                                    </>
                                )}
                            </Button>
                            <Button
                                variant="outline"
                                size="lg"
                                onClick={() => { setShowSetup(false); setSetupError(""); }}
                                disabled={isStarting}
                            >
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
