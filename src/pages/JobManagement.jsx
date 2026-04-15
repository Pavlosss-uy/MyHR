import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import JobCandidatesTab from "@/components/hr/JobCandidatesTab";
import { createJob, getJobs } from "@/lib/interviewApi";
import { useToast } from "@/hooks/use-toast";
import {
    Plus,
    Briefcase,
    Users,
    BarChart3,
    Loader2,
    FileText,
    ChevronRight,
    Sparkles,
    ArrowLeft,
    X,
} from "lucide-react";

/** ── TabButton ──────────────────────────────────────────────────────────── */
const TabButton = ({ active, onClick, children }) => (
    <button
        onClick={onClick}
        className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${
            active
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
        }`}
    >
        {children}
    </button>
);

const JobManagement = () => {
    const { toast } = useToast();

    // View state: "list" | "detail"
    const [view, setView] = useState("list");
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedJob, setSelectedJob] = useState(null);
    const [activeTab, setActiveTab] = useState("candidates");

    // Create job modal
    const [showCreate, setShowCreate] = useState(false);
    const [creating, setCreating] = useState(false);

    // Fetch jobs
    const fetchJobs = useCallback(async () => {
        setLoading(true);
        try {
            const data = await getJobs();
            setJobs(data.jobs || []);
        } catch (err) {
            toast({ title: "Error", description: err.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [toast]);

    useEffect(() => { fetchJobs(); }, [fetchJobs]);

    // Create job handler
    const handleCreateJob = async (e) => {
        e.preventDefault();
        setCreating(true);

        const data = new FormData(e.target);
        try {
            const result = await createJob({
                title: (data.get("title") ?? "").trim(),
                description: (data.get("description") ?? "").trim(),
            });
            toast({ title: "Job Created", description: `"${result.title}" created with ${result.extractedSkills?.length || 0} skills extracted.` });
            setShowCreate(false);
            fetchJobs();
        } catch (err) {
            toast({ title: "Error", description: err.message, variant: "destructive" });
        } finally {
            setCreating(false);
        }
    };

    // Open job detail
    const openJob = (job) => {
        setSelectedJob(job);
        setActiveTab("candidates");
        setView("detail");
    };

    /* ═══════════════════════════════════════════════════════════════════════ */
    /*  DETAIL VIEW                                                          */
    /* ═══════════════════════════════════════════════════════════════════════ */

    if (view === "detail" && selectedJob) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <main className="pt-24 pb-12 max-w-6xl mx-auto px-6">
                    {/* Back + title */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mb-6"
                    >
                        <button
                            onClick={() => setView("list")}
                            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-3"
                        >
                            <ArrowLeft className="w-4 h-4" />
                            Back to Jobs
                        </button>

                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <div>
                                <h1 className="text-2xl font-bold text-foreground">{selectedJob.title}</h1>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                    {selectedJob.stats?.totalCandidates || 0} candidates ·{" "}
                                    {selectedJob.stats?.interviewed || 0} interviewed
                                </p>
                            </div>

                            <span
                                className={`self-start text-xs font-semibold px-2.5 py-1 rounded-full ${
                                    selectedJob.status === "active"
                                        ? "bg-mint/10 text-mint-dark border border-mint/20"
                                        : "bg-muted text-muted-foreground"
                                }`}
                            >
                                {selectedJob.status || "active"}
                            </span>
                        </div>
                    </motion.div>

                    {/* Tabs */}
                    <div className="flex items-center gap-2 mb-6 border-b border-border pb-3">
                        <TabButton active={activeTab === "candidates"} onClick={() => setActiveTab("candidates")}>
                            <Users className="w-4 h-4 inline mr-1.5 -mt-0.5" />
                            Candidates
                        </TabButton>
                        <TabButton active={activeTab === "overview"} onClick={() => setActiveTab("overview")}>
                            <FileText className="w-4 h-4 inline mr-1.5 -mt-0.5" />
                            Overview
                        </TabButton>
                        <TabButton active={activeTab === "settings"} onClick={() => setActiveTab("settings")}>
                            <BarChart3 className="w-4 h-4 inline mr-1.5 -mt-0.5" />
                            Settings
                        </TabButton>
                    </div>

                    {/* Tab content */}
                    {activeTab === "candidates" && (
                        <JobCandidatesTab
                            jobId={selectedJob.id}
                            jobTitle={selectedJob.title}
                            extractedSkills={selectedJob.extractedSkills || []}
                        />
                    )}

                    {activeTab === "overview" && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="space-y-6"
                        >
                            {/* JD text */}
                            <div className="bg-card rounded-xl border border-border p-6">
                                <h3 className="font-semibold text-foreground mb-3">Job Description</h3>
                                <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
                                    {selectedJob.description || "No description available."}
                                </p>
                            </div>

                            {/* Extracted skills */}
                            {selectedJob.extractedSkills?.length > 0 && (
                                <div className="bg-card rounded-xl border border-border p-6">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Sparkles className="w-4 h-4 text-mint" />
                                        <h3 className="font-semibold text-foreground">AI-Extracted Skills</h3>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {selectedJob.extractedSkills.map((skill) => (
                                            <span
                                                key={skill}
                                                className="px-3 py-1.5 rounded-lg text-sm font-medium bg-cobalt/10 text-cobalt border border-cobalt/20"
                                            >
                                                {skill}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Stats */}
                            <div className="grid grid-cols-3 gap-4">
                                {[
                                    { label: "Candidates", value: selectedJob.stats?.totalCandidates || 0, icon: Users },
                                    { label: "Interviewed", value: selectedJob.stats?.interviewed || 0, icon: BarChart3 },
                                    { label: "Avg Match", value: `${selectedJob.stats?.avgMatchScore || 0}%`, icon: Sparkles },
                                ].map((stat) => (
                                    <div key={stat.label} className="bg-card rounded-xl border border-border p-4 text-center">
                                        <stat.icon className="w-5 h-5 text-cobalt-light mx-auto mb-2" />
                                        <p className="text-2xl font-bold text-foreground">{stat.value}</p>
                                        <p className="text-xs text-muted-foreground">{stat.label}</p>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    )}

                    {activeTab === "settings" && (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                            <div className="bg-card rounded-xl border border-border p-6 text-center text-muted-foreground text-sm">
                                Job settings (close job, edit description, etc.) will be available here.
                            </div>
                        </motion.div>
                    )}
                </main>
            </div>
        );
    }

    /* ═══════════════════════════════════════════════════════════════════════ */
    /*  LIST VIEW                                                            */
    /* ═══════════════════════════════════════════════════════════════════════ */

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
                        <h1 className="text-2xl font-bold text-foreground">Job Management</h1>
                        <p className="text-muted-foreground mt-1">Create jobs, upload CVs, and rank candidates with AI.</p>
                    </div>
                    <Button variant="hero" onClick={() => setShowCreate(true)}>
                        <Plus className="w-4 h-4 mr-1.5" />
                        New Job
                    </Button>
                </motion.div>

                {/* Create Job Modal */}
                <AnimatePresence>
                    {showCreate && (
                        <>
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
                                onClick={() => setShowCreate(false)}
                            />
                            <motion.div
                                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: 20, scale: 0.95 }}
                                className="fixed inset-0 z-50 flex items-center justify-center px-4"
                                style={{ pointerEvents: "none" }}
                            >
                            <div className="w-full max-w-lg" style={{ pointerEvents: "auto" }}>
                                <form
                                    onSubmit={handleCreateJob}
                                    className="bg-card rounded-2xl border border-border p-6 shadow-xl space-y-5"
                                >
                                    <div className="flex items-center justify-between">
                                        <h2 className="font-bold text-foreground text-lg">Create New Job</h2>
                                        <button
                                            type="button"
                                            onClick={() => setShowCreate(false)}
                                            className="p-1.5 rounded-lg hover:bg-muted"
                                        >
                                            <X className="w-4 h-4 text-muted-foreground" />
                                        </button>
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="jobTitle">Job Title</Label>
                                        <Input id="jobTitle" name="title" placeholder="Senior Software Engineer" required className="h-11" />
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="jobDescription">Job Description</Label>
                                        <textarea
                                            id="jobDescription"
                                            name="description"
                                            rows={6}
                                            placeholder="Paste the full job description here..."
                                            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                                            required
                                        />
                                        <p className="text-[11px] text-muted-foreground">
                                            AI will automatically extract key skills from the description.
                                        </p>
                                    </div>

                                    <div className="flex gap-3 justify-end">
                                        <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>
                                            Cancel
                                        </Button>
                                        <Button type="submit" variant="hero" disabled={creating}>
                                            {creating ? (
                                                <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> Creating...</>
                                            ) : (
                                                <><Sparkles className="w-4 h-4 mr-1.5" /> Create Job</>
                                            )}
                                        </Button>
                                    </div>
                                </form>
                            </div>
                            </motion.div>
                        </>
                    )}
                </AnimatePresence>

                {/* Jobs list */}
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
                    </div>
                ) : jobs.length === 0 ? (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="text-center py-20"
                    >
                        <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
                            <Briefcase className="w-8 h-8 text-muted-foreground" />
                        </div>
                        <h3 className="font-semibold text-foreground mb-1">No jobs yet</h3>
                        <p className="text-sm text-muted-foreground mb-6">Create your first job posting to start matching candidates.</p>
                        <Button variant="hero" onClick={() => setShowCreate(true)}>
                            <Plus className="w-4 h-4 mr-1.5" />
                            Create First Job
                        </Button>
                    </motion.div>
                ) : (
                    <div className="space-y-3">
                        {jobs.map((job, i) => (
                            <motion.button
                                key={job.id}
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.05 }}
                                onClick={() => openJob(job)}
                                className="w-full bg-card rounded-xl border border-border p-5 hover:border-cobalt-lighter/30 hover:shadow-cobalt transition-all duration-200 text-left group"
                            >
                                <div className="flex items-center gap-4">
                                    <div className="w-11 h-11 rounded-xl gradient-cobalt flex items-center justify-center shadow-sm shrink-0">
                                        <Briefcase className="w-5 h-5 text-primary-foreground" />
                                    </div>

                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-semibold text-foreground group-hover:text-cobalt transition-colors truncate">
                                            {job.title}
                                        </h3>
                                        <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                                            <span className="flex items-center gap-1">
                                                <Users className="w-3 h-3" />
                                                {job.stats?.totalCandidates || 0} candidates
                                            </span>
                                            <span className="flex items-center gap-1">
                                                <BarChart3 className="w-3 h-3" />
                                                {job.stats?.interviewed || 0} interviewed
                                            </span>
                                            {job.stats?.avgMatchScore > 0 && (
                                                <span className="flex items-center gap-1">
                                                    <Sparkles className="w-3 h-3 text-mint" />
                                                    {Math.round(job.stats.avgMatchScore)}% avg match
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* Skills preview */}
                                    {job.extractedSkills?.length > 0 && (
                                        <div className="hidden lg:flex items-center gap-1.5">
                                            {job.extractedSkills.slice(0, 3).map((s) => (
                                                <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-cobalt/10 text-cobalt">
                                                    {s}
                                                </span>
                                            ))}
                                            {job.extractedSkills.length > 3 && (
                                                <span className="text-[10px] text-muted-foreground">+{job.extractedSkills.length - 3}</span>
                                            )}
                                        </div>
                                    )}

                                    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-cobalt-light transition-all group-hover:translate-x-0.5" />
                                </div>
                            </motion.button>
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
};

export default JobManagement;
