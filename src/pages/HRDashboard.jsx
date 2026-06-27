import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import { Users, Briefcase, BarChart3, Plus, Loader2, Shield, CheckCircle2, Clock, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link, useNavigate } from "react-router-dom";
import { getJobs } from "@/lib/interviewApi";

const HRDashboard = () => {
    const { user, loading: authLoading, isAdmin } = useAuth();
    const navigate = useNavigate();
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [fetchError, setFetchError] = useState(null);
    const [retryTick, setRetryTick] = useState(0);

    useEffect(() => {
        if (!authLoading && isAdmin) {
            navigate("/admin/requests", { replace: true });
        }
    }, [isAdmin, authLoading, navigate]);

    useEffect(() => {
        if (authLoading) return;
        if (!user?.uid) { setLoading(false); return; }
        let cancelled = false;
        setFetchError(null);
        setLoading(true);
        (async () => {
            try {
                await user.getIdToken();
                const data = await getJobs();
                if (!cancelled) setJobs(data.jobs || []);
            } catch (err) {
                if (!cancelled && retryTick === 0) {
                    setTimeout(() => { if (!cancelled) setRetryTick(1); }, 800);
                    return;
                }
                if (!cancelled) setFetchError("Failed to load jobs.");
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [user?.uid, authLoading, retryTick]);

    const activeJobs = jobs.filter((j) => j.status !== "closed");
    const closedJobs = jobs.filter((j) => j.status === "closed");

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-7xl mx-auto px-6">

                {/* Header */}
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-bold text-foreground">HR Dashboard</h1>
                        <p className="text-muted-foreground mt-1">Your open roles and candidate pipelines at a glance.</p>
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

                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
                    </div>
                ) : fetchError ? (
                    <div className="text-center py-20">
                        <p className="text-sm text-destructive mb-3">{fetchError}</p>
                        <Button variant="outline" size="sm" onClick={() => setRetryTick((t) => t + 1)}>Retry</Button>
                    </div>
                ) : jobs.length === 0 ? (
                    <div className="text-center py-20">
                        <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
                            <Briefcase className="w-8 h-8 text-muted-foreground" />
                        </div>
                        <h3 className="font-semibold text-foreground mb-1">No job postings yet</h3>
                        <p className="text-sm text-muted-foreground mb-4">Create your first role to start evaluating candidates.</p>
                        <Button variant="hero" size="sm" asChild>
                            <Link to="/hr/jobs"><Plus className="w-4 h-4 mr-1" />Create Job</Link>
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-8">

                        {/* Active roles */}
                        {activeJobs.length > 0 && (
                            <section>
                                <div className="flex items-center justify-between mb-4">
                                    <h2 className="font-semibold text-foreground">
                                        Active Roles
                                        <span className="ml-2 text-xs font-normal text-muted-foreground">({activeJobs.length})</span>
                                    </h2>
                                    <Button variant="ghost" size="sm" asChild>
                                        <Link to="/hr/jobs">Manage all <ChevronRight className="w-3.5 h-3.5 ml-1" /></Link>
                                    </Button>
                                </div>
                                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {activeJobs.map((job, i) => (
                                        <JobCard key={job.id} job={job} index={i} />
                                    ))}
                                </div>
                            </section>
                        )}

                        {/* Closed roles */}
                        {closedJobs.length > 0 && (
                            <section>
                                <h2 className="font-semibold text-foreground mb-4">
                                    Closed Roles
                                    <span className="ml-2 text-xs font-normal text-muted-foreground">({closedJobs.length})</span>
                                </h2>
                                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {closedJobs.map((job, i) => (
                                        <JobCard key={job.id} job={job} index={i} closed />
                                    ))}
                                </div>
                            </section>
                        )}

                    </div>
                )}
            </main>
        </div>
    );
};

// ── Per-job stat card ──────────────────────────────────────────────────────────

const JobCard = ({ job, index = 0, closed = false }) => {
    const candidates  = job.stats?.totalCandidates || 0;
    const interviewed = job.stats?.interviewed || 0;
    const matchScore  = job.stats?.avgMatchScore ? Math.round(job.stats.avgMatchScore) : null;
    const pending     = candidates - interviewed;

    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04 }}
        >
            <Link
                to={`/hr/jobs?jobId=${job.id}`}
                className={`block bg-card rounded-xl border p-5 hover:shadow-md transition-all duration-200 ${
                    closed ? "border-border opacity-70 hover:opacity-90" : "border-border hover:border-cobalt-lighter/40 hover:shadow-cobalt"
                }`}
            >
                {/* Title row */}
                <div className="flex items-start justify-between gap-2 mb-4">
                    <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${closed ? "bg-muted" : "gradient-cobalt"}`}>
                            <Briefcase className={`w-4 h-4 ${closed ? "text-muted-foreground" : "text-primary-foreground"}`} />
                        </div>
                        <p className="text-sm font-semibold text-foreground truncate">{job.title}</p>
                    </div>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${
                        closed ? "bg-muted text-muted-foreground" : "bg-mint/10 text-mint-dark"
                    }`}>
                        {closed ? "closed" : "active"}
                    </span>
                </div>

                {/* 3 per-job stats */}
                <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="bg-muted/50 rounded-lg py-2.5">
                        <div className="flex items-center justify-center gap-1 mb-0.5">
                            <Users className="w-3 h-3 text-muted-foreground" />
                        </div>
                        <p className="text-base font-bold text-foreground">{candidates}</p>
                        <p className="text-[10px] text-muted-foreground">Candidates</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg py-2.5">
                        <div className="flex items-center justify-center gap-1 mb-0.5">
                            <CheckCircle2 className="w-3 h-3 text-mint" />
                        </div>
                        <p className="text-base font-bold text-foreground">{interviewed}</p>
                        <p className="text-[10px] text-muted-foreground">Interviewed</p>
                    </div>
                    <div className="bg-muted/50 rounded-lg py-2.5">
                        <div className="flex items-center justify-center gap-1 mb-0.5">
                            <Clock className="w-3 h-3 text-warning" />
                        </div>
                        <p className="text-base font-bold text-foreground">{pending}</p>
                        <p className="text-[10px] text-muted-foreground">Pending</p>
                    </div>
                </div>

                {/* Match score bar */}
                {matchScore !== null && (
                    <div className="mt-3">
                        <div className="flex justify-between text-xs text-muted-foreground mb-1">
                            <span>Avg CV Match</span>
                            <span className="font-semibold text-foreground">{matchScore}%</span>
                        </div>
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full ${matchScore >= 70 ? "bg-mint" : matchScore >= 50 ? "gradient-cobalt" : "bg-warning"}`}
                                style={{ width: `${matchScore}%` }}
                            />
                        </div>
                    </div>
                )}
            </Link>
        </motion.div>
    );
};

export default HRDashboard;
