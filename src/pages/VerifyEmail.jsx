import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { sendEmailVerification } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { useAuth } from "@/contexts/AuthContext";
import { Brain, MailCheck, RefreshCw, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

const VerifyEmail = () => {
    const { user, refreshUser, logout } = useAuth();
    const navigate = useNavigate();
    const [resending, setResending]     = useState(false);
    const [checking,  setChecking]      = useState(false);
    const [resent,    setResent]        = useState(false);
    const [error,     setError]         = useState("");

    const role = sessionStorage.getItem("myhr_role") || "";
    const dest  = role === "hr" ? "/hr/dashboard" : "/candidate";

    const handleResend = async () => {
        setResending(true);
        setError("");
        try {
            if (auth.currentUser) await sendEmailVerification(auth.currentUser);
            setResent(true);
        } catch (err) {
            setError(err.code === "auth/too-many-requests"
                ? "Too many requests — please wait a moment before trying again."
                : "Failed to resend. Please try again.");
        } finally {
            setResending(false);
        }
    };

    const handleCheckVerification = async () => {
        setChecking(true);
        setError("");
        try {
            await refreshUser();
            if (auth.currentUser?.emailVerified) {
                navigate(dest, { replace: true });
            } else {
                setError("Email not yet verified. Check your inbox (including spam).");
            }
        } catch {
            setError("Something went wrong. Please try again.");
        } finally {
            setChecking(false);
        }
    };

    const handleLogout = async () => {
        await logout();
        navigate("/", { replace: true });
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
            <div className="absolute inset-0 gradient-hero" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(160_60%_45%/0.08),transparent_60%)]" />

            <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.45 }}
                className="relative w-full max-w-md"
            >
                <div className="glass-strong rounded-2xl p-8 space-y-6 text-center">
                    {/* Logo */}
                    <div className="flex items-center justify-center gap-2.5">
                        <div className="w-10 h-10 rounded-xl gradient-cobalt flex items-center justify-center shadow-cobalt">
                            <Brain className="w-5 h-5 text-primary-foreground" />
                        </div>
                        <span className="text-xl font-bold text-foreground">
                            My<span className="text-cobalt-light">HR</span>
                        </span>
                    </div>

                    {/* Icon */}
                    <div className="flex items-center justify-center">
                        <div className="w-16 h-16 rounded-2xl bg-cobalt/10 flex items-center justify-center">
                            <MailCheck className="w-8 h-8 text-cobalt-light" />
                        </div>
                    </div>

                    {/* Copy */}
                    <div className="space-y-2">
                        <h1 className="text-xl font-bold text-foreground">Verify your email</h1>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                            We sent a verification link to{" "}
                            <span className="font-medium text-foreground">{user?.email}</span>.
                            <br />
                            Click the link in that email, then come back here.
                        </p>
                    </div>

                    {/* Error */}
                    {error && (
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2"
                        >
                            {error}
                        </motion.p>
                    )}

                    {/* Resent confirmation */}
                    {resent && !error && (
                        <p className="text-sm text-mint">Email resent — check your inbox.</p>
                    )}

                    {/* Actions */}
                    <div className="space-y-3">
                        <Button
                            variant="hero"
                            className="w-full h-11"
                            onClick={handleCheckVerification}
                            disabled={checking}
                        >
                            {checking ? (
                                <span className="flex items-center gap-2">
                                    <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                    Checking…
                                </span>
                            ) : (
                                <span className="flex items-center gap-2">
                                    <RefreshCw className="w-4 h-4" />
                                    I've verified — continue
                                </span>
                            )}
                        </Button>

                        <Button
                            variant="outline"
                            className="w-full h-11"
                            onClick={handleResend}
                            disabled={resending}
                        >
                            {resending ? "Sending…" : "Resend verification email"}
                        </Button>

                        <button
                            onClick={handleLogout}
                            className="flex items-center gap-1.5 mx-auto text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                            <LogOut className="w-3.5 h-3.5" />
                            Sign out and use a different account
                        </button>
                    </div>
                </div>
            </motion.div>
        </div>
    );
};

export default VerifyEmail;
