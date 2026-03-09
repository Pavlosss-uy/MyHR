import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import Navbar from "@/components/Navbar";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    Briefcase,
    Loader2,
    CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

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

    // Modal state
    const [showSetupModal, setShowSetupModal] = useState(false);
    const [cvFile, setCvFile] = useState(null);
    const [jobDescription, setJobDescription] = useState("");
    const [isStarting, setIsStarting] = useState(false);

    const handleCvUpload = (e) => {
        const file = e.target.files?.[0];
        if (file && file.type === "application/pdf") {
            setCvFile(file);
        }
    };

    const handleRemoveCv = () => {
        setCvFile(null);
    };

    const handleStartInterview = async () => {
        setIsStarting(true);
        // Mock delay — later this will send CV + JD to the backend
        await new Promise((resolve) => setTimeout(resolve, 1200));
        setIsStarting(false);
        setShowSetupModal(false);
        navigate("/interview");
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
                                    onClick={() => setShowSetupModal(true)}
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
                            <Button
                                variant="hero"
                                size="sm"
                                className="mt-4 w-full"
                                onClick={() => setShowSetupModal(true)}
                            >
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
            <AnimatePresence>
                {showSetupModal && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
                        onClick={(e) => {
                            if (e.target === e.currentTarget) setShowSetupModal(false);
                        }}
                    >
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 20 }}
                            transition={{ duration: 0.25 }}
                            className="w-full max-w-lg bg-card rounded-2xl border border-border shadow-cobalt-lg overflow-hidden"
                        >
                            {/* Header */}
                            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
                                <div className="flex items-center gap-3">
                                    <div className="w-9 h-9 rounded-xl gradient-cobalt flex items-center justify-center shadow-cobalt">
                                        <Mic className="w-4 h-4 text-primary-foreground" />
                                    </div>
                                    <div>
                                        <h2 className="text-lg font-semibold text-foreground">Setup Your Interview</h2>
                                        <p className="text-xs text-muted-foreground">Upload your CV and provide the job description</p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setShowSetupModal(false)}
                                    className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            </div>

                            {/* Body */}
                            <div className="px-6 py-5 space-y-5">
                                {/* CV Upload */}
                                <div className="space-y-2">
                                    <Label className="text-sm font-medium text-foreground flex items-center gap-2">
                                        <Upload className="w-4 h-4 text-cobalt-light" />
                                        Upload Your CV (PDF)
                                    </Label>
                                    {cvFile ? (
                                        <div className="flex items-center gap-3 p-3 rounded-xl border border-mint/30 bg-mint/5">
                                            <div className="w-10 h-10 rounded-lg bg-mint/15 flex items-center justify-center">
                                                <FileText className="w-5 h-5 text-mint" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium text-foreground truncate">{cvFile.name}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {(cvFile.size / 1024).toFixed(1)} KB · PDF
                                                </p>
                                            </div>
                                            <button
                                                onClick={handleRemoveCv}
                                                className="w-7 h-7 rounded-full flex items-center justify-center text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                                            >
                                                <X className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    ) : (
                                        <label className="flex flex-col items-center gap-2 p-6 rounded-xl border-2 border-dashed border-border hover:border-cobalt-lighter/40 hover:bg-muted/30 cursor-pointer transition-all">
                                            <div className="w-12 h-12 rounded-xl bg-cobalt/10 flex items-center justify-center">
                                                <Upload className="w-5 h-5 text-cobalt-light" />
                                            </div>
                                            <div className="text-center">
                                                <p className="text-sm font-medium text-foreground">Click to upload PDF</p>
                                                <p className="text-xs text-muted-foreground mt-0.5">or drag and drop</p>
                                            </div>
                                            <input
                                                type="file"
                                                accept=".pdf,application/pdf"
                                                onChange={handleCvUpload}
                                                className="hidden"
                                            />
                                        </label>
                                    )}
                                </div>

                                {/* Job Description */}
                                <div className="space-y-2">
                                    <Label className="text-sm font-medium text-foreground flex items-center gap-2">
                                        <Briefcase className="w-4 h-4 text-cobalt-light" />
                                        Job Description
                                    </Label>
                                    <textarea
                                        value={jobDescription}
                                        onChange={(e) => setJobDescription(e.target.value)}
                                        placeholder="Paste the job description here... e.g. responsibilities, required skills, qualifications"
                                        rows={5}
                                        className="w-full rounded-xl border border-input bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none leading-relaxed"
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Our AI will extract key competencies and generate tailored interview questions.
                                    </p>
                                </div>
                            </div>

                            {/* Footer */}
                            <div className="px-6 py-4 border-t border-border bg-muted/20 flex items-center justify-between">
                                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                    <span className="flex items-center gap-1">
                                        {cvFile ? (
                                            <CheckCircle2 className="w-3.5 h-3.5 text-mint" />
                                        ) : (
                                            <div className="w-3.5 h-3.5 rounded-full border border-border" />
                                        )}
                                        CV
                                    </span>
                                    <span className="flex items-center gap-1">
                                        {jobDescription.trim().length > 10 ? (
                                            <CheckCircle2 className="w-3.5 h-3.5 text-mint" />
                                        ) : (
                                            <div className="w-3.5 h-3.5 rounded-full border border-border" />
                                        )}
                                        Job Description
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setShowSetupModal(false)}
                                    >
                                        Cancel
                                    </Button>
                                    <Button
                                        variant="hero"
                                        size="sm"
                                        onClick={handleStartInterview}
                                        disabled={isStarting || !cvFile || jobDescription.trim().length < 10}
                                        className="gap-2"
                                        title={!cvFile || jobDescription.trim().length < 10 ? "Please upload a CV and enter a job description" : ""}
                                    >
                                        {isStarting ? (
                                            <>
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                Preparing...
                                            </>
                                        ) : (
                                            <>
                                                Start Interview
                                                <ArrowRight className="w-4 h-4" />
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default CandidateHome;
