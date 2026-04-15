import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { getPendingRequests, acceptAccessRequest, rejectAccessRequest } from "@/lib/interviewApi";
import {
    Users,
    Building2,
    Mail,
    CheckCircle2,
    XCircle,
    Clock,
    Loader2,
    RefreshCw,
    Copy,
    ExternalLink,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const statusStyles = {
    pending: "bg-warning/10 text-warning border-warning/20",
    accepted: "bg-mint/10 text-mint-dark border-mint/20",
    rejected: "bg-destructive/10 text-destructive border-destructive/20",
};

const AdminPendingRequests = () => {
    const { toast } = useToast();
    const [requests, setRequests] = useState([]);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState("");
    const [invitationLink, setInvitationLink] = useState("");

    const fetchRequests = async () => {
        setLoading(true);
        try {
            const data = await getPendingRequests();
            setRequests(data.requests || []);
        } catch (err) {
            toast({ title: "Error", description: err.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchRequests(); }, []);

    const handleAccept = async (requestId) => {
        setProcessing(requestId);
        try {
            const result = await acceptAccessRequest(requestId);
            setInvitationLink(result.invitationLink || "");
            toast({ title: "Request Accepted", description: "Invitation link generated." });
            fetchRequests();
        } catch (err) {
            toast({ title: "Error", description: err.message, variant: "destructive" });
        } finally {
            setProcessing("");
        }
    };

    const handleReject = async (requestId) => {
        setProcessing(requestId);
        try {
            await rejectAccessRequest(requestId);
            toast({ title: "Request Rejected" });
            fetchRequests();
        } catch (err) {
            toast({ title: "Error", description: err.message, variant: "destructive" });
        } finally {
            setProcessing("");
        }
    };

    const copyLink = () => {
        navigator.clipboard.writeText(invitationLink);
        toast({ title: "Copied!", description: "Invitation link copied to clipboard." });
    };

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
                        <h1 className="text-2xl font-bold text-foreground">Access Requests</h1>
                        <p className="text-muted-foreground mt-1">Review and approve enterprise access requests.</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={fetchRequests} disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                </motion.div>

                {/* Invitation link banner */}
                <AnimatePresence>
                    {invitationLink && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="mb-6 bg-mint/10 border border-mint/20 rounded-xl p-4 flex items-center gap-3"
                        >
                            <ExternalLink className="w-5 h-5 text-mint shrink-0" />
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-foreground">Invitation Link Generated</p>
                                <p className="text-xs text-muted-foreground truncate">{invitationLink}</p>
                            </div>
                            <Button variant="outline" size="sm" onClick={copyLink}>
                                <Copy className="w-3.5 h-3.5 mr-1" />
                                Copy
                            </Button>
                            <button
                                onClick={() => setInvitationLink("")}
                                className="text-muted-foreground hover:text-foreground"
                            >
                                <XCircle className="w-4 h-4" />
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Loading state */}
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
                    </div>
                ) : requests.length === 0 ? (
                    <div className="text-center py-20">
                        <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
                            <Clock className="w-8 h-8 text-muted-foreground" />
                        </div>
                        <h3 className="font-semibold text-foreground mb-1">No pending requests</h3>
                        <p className="text-sm text-muted-foreground">New requests will appear here.</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {requests.map((req, i) => (
                            <motion.div
                                key={req.id}
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.05 }}
                                className="bg-card rounded-xl border border-border p-5 hover:shadow-sm transition-shadow"
                            >
                                <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                                    <div className="flex-1 space-y-2">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-lg gradient-cobalt flex items-center justify-center">
                                                <Building2 className="w-5 h-5 text-primary-foreground" />
                                            </div>
                                            <div>
                                                <h3 className="font-semibold text-foreground">{req.companyName}</h3>
                                                <p className="text-xs text-muted-foreground">{req.contactName}</p>
                                            </div>
                                        </div>

                                        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                                            <span className="flex items-center gap-1.5">
                                                <Mail className="w-3.5 h-3.5" />
                                                {req.contactEmail}
                                            </span>
                                            <span className="flex items-center gap-1.5">
                                                <Users className="w-3.5 h-3.5" />
                                                {req.companySize} employees
                                            </span>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handleReject(req.id)}
                                            disabled={processing === req.id}
                                            className="text-destructive hover:text-destructive"
                                        >
                                            {processing === req.id ? (
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <>
                                                    <XCircle className="w-4 h-4 mr-1" />
                                                    Reject
                                                </>
                                            )}
                                        </Button>
                                        <Button
                                            variant="hero"
                                            size="sm"
                                            onClick={() => handleAccept(req.id)}
                                            disabled={processing === req.id}
                                        >
                                            {processing === req.id ? (
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <>
                                                    <CheckCircle2 className="w-4 h-4 mr-1" />
                                                    Approve
                                                </>
                                            )}
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
};

export default AdminPendingRequests;
