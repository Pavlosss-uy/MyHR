import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import StatCard from "@/components/StatCard";
import CircularProgress from "@/components/CircularProgress";
import { Users, Briefcase, Clock, TrendingUp, Star, MoreHorizontal, Play, BarChart3, Plus, Loader2, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { getJobs } from "@/lib/interviewApi";

const statusColors = {
    Recommended: "bg-mint-light text-mint-dark",
    "Under Review": "bg-warning/10 text-warning",
    "Needs Improvement": "bg-destructive/10 text-destructive",
};

const getStatus = (score) => {
    if (score >= 85) return "Recommended";
    if (score >= 60) return "Under Review";
    return "Needs Improvement";
};

const HRDashboard = () => {
    const { user, loading: authLoading, isAdmin } = useAuth();
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (authLoading) return;
        if (!user?.accessToken) { setLoading(false); return; }
        let cancelled = false;
        (async () => {
            try {
                const data = await getJobs();
                if (!cancelled) setJobs(data.jobs || []);
            } catch (err) {
                console.error("Failed to load jobs:", err);
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [user?.accessToken, authLoading]);

    // Aggregate stats from jobs
    const totalCandidates = jobs.reduce((sum, j) => sum + (j.stats?.totalCandidates || 0), 0);
    const openPositions = jobs.filter((j) => j.status === "active").length;
    const totalInterviewed = jobs.reduce((sum, j) => sum + (j.stats?.interviewed || 0), 0);
    const avgMatch = jobs.length > 0
        ? Math.round(jobs.reduce((sum, j) => sum + (j.stats?.avgMatchScore || 0), 0) / jobs.length)
        : 0;

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-7xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
                >
                    <div>
                        <h1 className="text-2xl font-bold text-foreground">HR Dashboard</h1>
                        <p className="text-muted-foreground mt-1">Overview of your hiring pipeline and candidate performance.</p>
                    </div>
                    <div className="flex gap-3">
                        {isAdmin && (
                            <Button variant="outline" size="sm" asChild>
                                <Link to="/admin/requests">
                                    <Shield className="w-4 h-4 mr-1.5" />
                                    Access Requests
                                </Link>
                            </Button>
                        )}
                        <Button variant="outline" size="sm" asChild>
                            <Link to="/hr/analytics">
                                <BarChart3 className="w-4 h-4 mr-1.5" />
                                Analytics
                            </Link>
                        </Button>
                        <Button variant="hero" size="sm" asChild>
                            <Link to="/hr/jobs">
                                <Plus className="w-4 h-4 mr-1.5" />
                                New Job
                            </Link>
                        </Button>
                    </div>
                </motion.div>

                {/* Stats Row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <StatCard icon={Users} label="Total Candidates" value={loading ? "—" : totalCandidates.toString()} change={totalCandidates > 0 ? `${totalCandidates} total` : ""} changeType="positive" />
                    <StatCard icon={Briefcase} label="Open Positions" value={loading ? "—" : openPositions.toString()} change={openPositions > 0 ? "active" : ""} changeType="positive" />
                    <StatCard icon={Clock} label="Interviewed" value={loading ? "—" : totalInterviewed.toString()} change={totalInterviewed > 0 ? "completed" : ""} changeType="positive" />
                    <StatCard icon={TrendingUp} label="Avg Match Score" value={loading ? "—" : `${avgMatch}%`} change={avgMatch > 70 ? "above threshold" : ""} changeType={avgMatch > 70 ? "positive" : "neutral"} />
                </div>

                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
                    </div>
                ) : (
                    <div className="grid lg:grid-cols-3 gap-6">
                        {/* Jobs overview */}
                        <div className="lg:col-span-2 bg-card rounded-xl border border-border shadow-sm">
                            <div className="p-5 border-b border-border flex items-center justify-between">
                                <div>
                                    <h2 className="font-semibold text-foreground">Active Jobs</h2>
                                    <p className="text-sm text-muted-foreground mt-0.5">Your open positions and candidate pipelines</p>
                                </div>
                                <Button variant="ghost" size="sm" asChild>
                                    <Link to="/hr/jobs">View All</Link>
                                </Button>
                            </div>

                            {jobs.length === 0 ? (
                                <div className="p-8 text-center">
                                    <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-3">
                                        <Briefcase className="w-7 h-7 text-muted-foreground" />
                                    </div>
                                    <p className="text-sm text-muted-foreground mb-3">No jobs yet. Create your first job posting.</p>
                                    <Button variant="hero" size="sm" asChild>
                                        <Link to="/hr/jobs">
                                            <Plus className="w-4 h-4 mr-1" />
                                            Create Job
                                        </Link>
                                    </Button>
                                </div>
                            ) : (
                                <div className="divide-y divide-border">
                                    {jobs.slice(0, 5).map((job) => (
                                        <Link
                                            key={job.id}
                                            to="/hr/jobs"
                                            className="block px-5 py-4 flex items-center justify-between hover:bg-muted/30 transition-colors"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-lg gradient-cobalt flex items-center justify-center">
                                                    <Briefcase className="w-4 h-4 text-primary-foreground" />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-medium text-foreground">{job.title}</p>
                                                    <p className="text-xs text-muted-foreground">
                                                        {job.stats?.totalCandidates || 0} candidates · {job.stats?.interviewed || 0} interviewed
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                {job.stats?.avgMatchScore > 0 && (
                                                    <div className="flex items-center gap-1.5">
                                                        <Star className="w-3.5 h-3.5 text-warning fill-warning" />
                                                        <span className="text-sm font-semibold text-foreground">
                                                            {Math.round(job.stats.avgMatchScore)}%
                                                        </span>
                                                    </div>
                                                )}
                                                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                                                    job.status === "active"
                                                        ? "bg-mint/10 text-mint-dark"
                                                        : "bg-muted text-muted-foreground"
                                                }`}>
                                                    {job.status || "active"}
                                                </span>
                                            </div>
                                        </Link>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Right Column */}
                        <div className="space-y-6">
                            {/* Hiring Health */}
                            <div className="bg-card rounded-xl border border-border shadow-sm p-5">
                                <h3 className="font-semibold text-foreground mb-4">Hiring Health</h3>
                                <div className="grid grid-cols-2 gap-4">
                                    <CircularProgress value={totalCandidates > 0 ? Math.min(100, Math.round(totalInterviewed / Math.max(totalCandidates, 1) * 100)) : 0} size={100} label="Pipeline" color="cobalt" />
                                    <CircularProgress value={avgMatch || 0} size={100} label="Quality" color="mint" />
                                </div>
                            </div>

                            {/* Quick actions */}
                            <div className="bg-card rounded-xl border border-border shadow-sm p-5 space-y-3">
                                <h3 className="font-semibold text-foreground">Quick Actions</h3>
                                <div className="space-y-2">
                                    <Button variant="outline" className="w-full justify-start" size="sm" asChild>
                                        <Link to="/hr/jobs">
                                            <Plus className="w-4 h-4 mr-2" />
                                            Create New Job
                                        </Link>
                                    </Button>
                                    {isAdmin && (
                                        <Button variant="outline" className="w-full justify-start" size="sm" asChild>
                                            <Link to="/admin/requests">
                                                <Shield className="w-4 h-4 mr-2" />
                                                Review Access Requests
                                            </Link>
                                        </Button>
                                    )}
                                    <Button variant="outline" className="w-full justify-start" size="sm" asChild>
                                        <Link to="/hr/analytics">
                                            <BarChart3 className="w-4 h-4 mr-2" />
                                            View Analytics
                                        </Link>
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
};

export default HRDashboard;
