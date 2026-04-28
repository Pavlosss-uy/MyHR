import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import CandidateCard from "@/components/hr/CandidateCard";
import MatchAnalysisDrawer from "@/components/hr/MatchAnalysisDrawer";
import { uploadCVs, getCandidates, inviteToInterview, deleteCandidate, updateCandidateStatus } from "@/lib/interviewApi";
import { useToast } from "@/hooks/use-toast";
import {
    Upload,
    Loader2,
    Users,
    Filter,
    ArrowUpDown,
    Brain,
    FileText,
    Copy,
    ExternalLink,
    X,
} from "lucide-react";

const JobCandidatesTab = ({ jobId, jobTitle }) => {
    const { toast } = useToast();
    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState("");
    const [loaded, setLoaded] = useState(false);

    const [sortBy, setSortBy] = useState("matchScore");
    const [statusFilter, setStatusFilter] = useState("");

    const [invitingId, setInvitingId] = useState("");
    const [decliningId, setDecliningId] = useState("");
    const [deletingId, setDeletingId] = useState("");
    const [lastInviteLink, setLastInviteLink] = useState({ name: "", link: "" });

    const [drawerCandidate, setDrawerCandidate] = useState(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [isDragging, setIsDragging] = useState(false);

    const fetchCandidates = useCallback(async () => {
        setLoading(true);
        try {
            const data = await getCandidates(jobId, sortBy, statusFilter);
            setCandidates(data.candidates || []);
            setLoaded(true);
        } catch (err) {
            toast({ title: "Error loading candidates", description: err.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [jobId, sortBy, statusFilter, toast]);

    useState(() => { fetchCandidates(); }, [fetchCandidates]);

    const handleUpload = async (files) => {
        if (!files || files.length === 0) return;
        setUploading(true);
        setUploadProgress(`Processing ${files.length} file(s)...`);
        try {
            const result = await uploadCVs(jobId, files);
            const msg = `${result.processed} CV(s) processed` + (result.failed > 0 ? `, ${result.failed} failed` : "");
            toast({ title: "Upload Complete", description: msg });
            setUploadProgress("");
            fetchCandidates();
        } catch (err) {
            toast({ title: "Upload Failed", description: err.message, variant: "destructive" });
            setUploadProgress("");
        } finally {
            setUploading(false);
        }
    };

    const handleFileInput = (e) => handleUpload(Array.from(e.target.files));

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        const files = Array.from(e.dataTransfer.files).filter(
            (f) => f.type === "application/pdf" || f.name.endsWith(".docx") || f.name.endsWith(".doc")
        );
        if (files.length > 0) handleUpload(files);
    };

    const handleInvite = async (candidate) => {
        setInvitingId(candidate.id);
        try {
            const result = await inviteToInterview(jobId, candidate.id);
            setLastInviteLink({ name: candidate.name, link: result.interviewLink || "" });
            toast({
                title: "Invitation Sent",
                description: candidate.email
                    ? `Email sent to ${candidate.email}`
                    : "Interview link generated — copy it below.",
            });
            fetchCandidates();
        } catch (err) {
            toast({ title: "Invitation Failed", description: err.message, variant: "destructive" });
        } finally {
            setInvitingId("");
        }
    };

    const handleDecline = async (candidate) => {
        setDecliningId(candidate.id);
        try {
            await updateCandidateStatus(jobId, candidate.id, "declined");
            toast({ title: "Candidate Declined", description: `${candidate.name} has been marked as declined.` });
            fetchCandidates();
            if (drawerCandidate?.id === candidate.id) setDrawerOpen(false);
        } catch (err) {
            toast({ title: "Decline Failed", description: err.message, variant: "destructive" });
        } finally {
            setDecliningId("");
        }
    };

    const handleDelete = async (candidate) => {
        const confirmed = window.confirm(
            `Permanently delete ${candidate.name}? This will remove their CV and any pending invitation. This cannot be undone.`
        );
        if (!confirmed) return;

        setDeletingId(candidate.id);
        try {
            await deleteCandidate(jobId, candidate.id);
            toast({ title: "Candidate Deleted", description: `${candidate.name} has been removed.` });
            setCandidates((prev) => prev.filter((c) => c.id !== candidate.id));
            if (drawerCandidate?.id === candidate.id) setDrawerOpen(false);
        } catch (err) {
            toast({ title: "Delete Failed", description: err.message, variant: "destructive" });
        } finally {
            setDeletingId("");
        }
    };

    return (
        <div className="space-y-6">
            {/* Upload Zone */}
            <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                    isDragging
                        ? "border-cobalt bg-cobalt/5"
                        : "border-border hover:border-cobalt-lighter hover:bg-muted/50"
                }`}
            >
                {uploading ? (
                    <div className="space-y-3">
                        <div className="w-14 h-14 rounded-2xl gradient-cobalt flex items-center justify-center mx-auto animate-pulse-glow shadow-cobalt">
                            <Brain className="w-7 h-7 text-primary-foreground" />
                        </div>
                        <p className="text-sm font-medium text-foreground">{uploadProgress || "Processing CVs..."}</p>
                        <div className="max-w-xs mx-auto">
                            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                                <div className="h-full gradient-cobalt rounded-full animate-shimmer" style={{ width: "70%" }} />
                            </div>
                        </div>
                    </div>
                ) : (
                    <label className="cursor-pointer space-y-3 block">
                        <div className="w-12 h-12 rounded-xl bg-primary/5 flex items-center justify-center mx-auto">
                            <Upload className="w-6 h-6 text-primary" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-foreground">
                                {isDragging ? "Drop files here" : "Upload Candidate CVs"}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                                Drag & drop or click to browse · PDF and DOCX supported · Multiple files
                            </p>
                        </div>
                        <Button variant="outline" size="sm" asChild>
                            <span>
                                <Upload className="w-3.5 h-3.5 mr-1.5" />
                                Browse Files
                            </span>
                        </Button>
                        <input
                            type="file"
                            multiple
                            accept=".pdf,.docx,.doc"
                            onChange={handleFileInput}
                            className="hidden"
                        />
                    </label>
                )}
            </div>

            {/* Controls bar */}
            {candidates.length > 0 && (
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Users className="w-4 h-4" />
                        <span>{candidates.length} candidate{candidates.length !== 1 ? "s" : ""}</span>
                    </div>

                    <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1.5">
                            <ArrowUpDown className="w-3.5 h-3.5 text-muted-foreground" />
                            <select
                                value={sortBy}
                                onChange={(e) => setSortBy(e.target.value)}
                                className="text-sm bg-transparent border border-border rounded-md px-2 py-1 text-foreground"
                            >
                                <option value="matchScore">Match Score</option>
                                <option value="totalScore">Total Score</option>
                                <option value="name">Name</option>
                            </select>
                        </div>

                        <div className="flex items-center gap-1.5">
                            <Filter className="w-3.5 h-3.5 text-muted-foreground" />
                            <select
                                value={statusFilter}
                                onChange={(e) => setStatusFilter(e.target.value)}
                                className="text-sm bg-transparent border border-border rounded-md px-2 py-1 text-foreground"
                            >
                                <option value="">All</option>
                                <option value="not_invited">Not Invited</option>
                                <option value="invited">Invited</option>
                                <option value="completed">Completed</option>
                                <option value="declined">Declined</option>
                                <option value="shortlisted">Shortlisted</option>
                            </select>
                        </div>

                        <Button variant="outline" size="sm" onClick={fetchCandidates} disabled={loading}>
                            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Refresh"}
                        </Button>
                    </div>
                </div>
            )}

            {/* Interview link banner */}
            {lastInviteLink.link && (
                <div className="bg-mint/10 border border-mint/20 rounded-xl p-4 flex items-center gap-3">
                    <ExternalLink className="w-5 h-5 text-mint shrink-0" />
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground">
                            Interview link for <span className="text-mint-dark">{lastInviteLink.name}</span>
                        </p>
                        <p className="text-xs text-muted-foreground truncate">{lastInviteLink.link}</p>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                            navigator.clipboard.writeText(lastInviteLink.link);
                            toast({ title: "Copied!", description: "Interview link copied to clipboard." });
                        }}
                    >
                        <Copy className="w-3.5 h-3.5 mr-1" />
                        Copy
                    </Button>
                    <button onClick={() => setLastInviteLink({ name: "", link: "" })} className="text-muted-foreground hover:text-foreground">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* Candidates grid */}
            {loading && !loaded ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
                </div>
            ) : candidates.length === 0 && loaded ? (
                <div className="text-center py-16">
                    <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
                        <FileText className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <h3 className="font-semibold text-foreground mb-1">No candidates yet</h3>
                    <p className="text-sm text-muted-foreground">Upload CVs above to start matching candidates.</p>
                </div>
            ) : (
                <div className="grid sm:grid-cols-2 gap-4">
                    {candidates.map((candidate, i) => (
                        <CandidateCard
                            key={candidate.id}
                            candidate={candidate}
                            index={i}
                            inviting={invitingId === candidate.id}
                            declining={decliningId === candidate.id}
                            deleting={deletingId === candidate.id}
                            onViewDetails={(c) => { setDrawerCandidate(c); setDrawerOpen(true); }}
                            onInvite={handleInvite}
                            onDecline={handleDecline}
                            onDelete={handleDelete}
                        />
                    ))}
                </div>
            )}

            {/* Match Analysis Drawer */}
            <MatchAnalysisDrawer
                candidate={drawerCandidate}
                jobTitle={jobTitle}
                isOpen={drawerOpen}
                onClose={() => setDrawerOpen(false)}
                onInvite={handleInvite}
                onDecline={handleDecline}
                declining={decliningId === drawerCandidate?.id}
            />
        </div>
    );
};

export default JobCandidatesTab;
