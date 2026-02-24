import { motion } from "framer-motion";
import { Link, useParams } from "react-router-dom";
import Navbar from "@/components/Navbar";
import CircularProgress from "@/components/CircularProgress";
import { Button } from "@/components/ui/button";
import {
    ArrowLeft,
    Mail,
    Phone,
    MapPin,
    Briefcase,
    Calendar,
    Star,
    Download,
    Play,
    CheckCircle2,
    AlertCircle
} from "lucide-react";

// Mock candidate data
const candidateData = {
    id: "1",
    name: "Sarah Chen",
    email: "sarah.chen@email.com",
    phone: "+1 (555) 123-4567",
    location: "San Francisco, CA",
    role: "Senior Engineer",
    appliedDate: "Jan 28, 2026",
    status: "Recommended",
    overallScore: 94,
    interviews: [
        { id: 1, date: "Feb 5, 2026", type: "Technical", score: 92, duration: "28 min" },
        { id: 2, date: "Feb 3, 2026", type: "Behavioral", score: 96, duration: "22 min" },
        { id: 3, date: "Jan 30, 2026", type: "Initial Screen", score: 94, duration: "15 min" },
    ],
    strengths: ["React & TypeScript expertise", "Strong system design skills", "Excellent communication"],
    improvements: ["Could elaborate more on leadership experience"],
};

const statusColors = {
    Recommended: "bg-mint-light text-mint-dark",
    "Under Review": "bg-warning/10 text-warning",
    "Needs Improvement": "bg-destructive/10 text-destructive",
};

const CandidateProfile = () => {
    const { id } = useParams();
    // In a real app, you'd fetch candidate data based on id
    const candidate = candidateData;

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-5xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
                        <Link to="/hr/dashboard">
                            <ArrowLeft className="w-4 h-4 mr-1" />
                            Back to Dashboard
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
                            {candidate.name.split(" ").map(n => n[0]).join("")}
                        </div>
                        <div className="flex-1">
                            <div className="flex flex-col md:flex-row md:items-center gap-3 mb-3">
                                <h1 className="text-2xl font-bold text-foreground">{candidate.name}</h1>
                                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${statusColors[candidate.status]}`}>
                                    {candidate.status}
                                </span>
                            </div>
                            <div className="grid sm:grid-cols-2 gap-3 text-sm text-muted-foreground">
                                <div className="flex items-center gap-2">
                                    <Mail className="w-4 h-4" />
                                    {candidate.email}
                                </div>
                                <div className="flex items-center gap-2">
                                    <Phone className="w-4 h-4" />
                                    {candidate.phone}
                                </div>
                                <div className="flex items-center gap-2">
                                    <MapPin className="w-4 h-4" />
                                    {candidate.location}
                                </div>
                                <div className="flex items-center gap-2">
                                    <Briefcase className="w-4 h-4" />
                                    {candidate.role}
                                </div>
                                <div className="flex items-center gap-2">
                                    <Calendar className="w-4 h-4" />
                                    Applied {candidate.appliedDate}
                                </div>
                            </div>
                        </div>
                        <div className="flex gap-2">
                            <Button variant="outline" size="sm">
                                <Download className="w-4 h-4 mr-1.5" />
                                Export
                            </Button>
                            <Button variant="hero" size="sm" asChild>
                                <Link to="/interview">Start Interview</Link>
                            </Button>
                        </div>
                    </div>
                </motion.div>

                <div className="grid lg:grid-cols-3 gap-6">
                    {/* Score Overview */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.15 }}
                        className="bg-card rounded-xl border border-border shadow-sm p-6 text-center"
                    >
                        <h3 className="font-semibold text-foreground mb-4">Overall Score</h3>
                        <CircularProgress value={candidate.overallScore} size={140} strokeWidth={10} color="mint" />
                        <p className="text-sm text-muted-foreground mt-4">Based on {candidate.interviews.length} interviews</p>
                    </motion.div>

                    {/* Strengths & Improvements */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="lg:col-span-2 bg-card rounded-xl border border-border shadow-sm"
                    >
                        <div className="p-5 border-b border-border">
                            <h3 className="font-semibold text-foreground">AI Assessment Summary</h3>
                        </div>
                        <div className="p-5 grid sm:grid-cols-2 gap-6">
                            <div>
                                <div className="flex items-center gap-2 mb-3">
                                    <CheckCircle2 className="w-4 h-4 text-mint" />
                                    <span className="text-sm font-medium text-foreground">Strengths</span>
                                </div>
                                <ul className="space-y-2">
                                    {candidate.strengths.map((s, i) => (
                                        <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                            <Star className="w-3 h-3 text-warning mt-1 shrink-0" />
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <div>
                                <div className="flex items-center gap-2 mb-3">
                                    <AlertCircle className="w-4 h-4 text-warning" />
                                    <span className="text-sm font-medium text-foreground">Areas for Improvement</span>
                                </div>
                                <ul className="space-y-2">
                                    {candidate.improvements.map((s, i) => (
                                        <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                            <div className="w-1.5 h-1.5 rounded-full bg-warning mt-2 shrink-0" />
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    </motion.div>
                </div>

                {/* Interview History */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.25 }}
                    className="mt-6 bg-card rounded-xl border border-border shadow-sm"
                >
                    <div className="p-5 border-b border-border">
                        <h3 className="font-semibold text-foreground">Interview History</h3>
                    </div>
                    <div className="divide-y divide-border">
                        {candidate.interviews.map((interview) => (
                            <div key={interview.id} className="px-5 py-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 rounded-lg bg-primary/5 flex items-center justify-center">
                                        <Play className="w-4 h-4 text-primary" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-foreground">{interview.type}</p>
                                        <p className="text-xs text-muted-foreground">{interview.date} · {interview.duration}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-4">
                                    <div className="flex items-center gap-1.5">
                                        <Star className="w-3.5 h-3.5 text-warning fill-warning" />
                                        <span className="text-sm font-semibold text-foreground">{interview.score}%</span>
                                    </div>
                                    <Button variant="ghost" size="sm" asChild>
                                        <Link to="/feedback">View Report</Link>
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>
                </motion.div>
            </main>
        </div>
    );
};

export default CandidateProfile;
