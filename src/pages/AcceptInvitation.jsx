import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
    createUserWithEmailAndPassword,
    updateProfile,
    sendEmailVerification,
} from "firebase/auth";
import { auth } from "@/lib/firebase";
import { validateInvitation, acceptInvitation, registerUserRole } from "@/lib/interviewApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Brain, ArrowRight, Lock, Mail, User, Loader2, AlertCircle, CheckCircle2, Clock } from "lucide-react";

const AcceptInvitation = () => {
    const { token } = useParams();
    const navigate = useNavigate();

    const [loading, setLoading] = useState(true);
    const [validating, setValidating] = useState(true);
    const [invitation, setInvitation] = useState(null);
    const [error, setError] = useState("");
    const [formError, setFormError] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Validate token on mount
    useEffect(() => {
        (async () => {
            try {
                const result = await validateInvitation(token);
                setInvitation(result);
            } catch (err) {
                setError(err.message || "Invalid invitation link.");
            } finally {
                setValidating(false);
                setLoading(false);
            }
        })();
    }, [token]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setFormError("");
        setIsSubmitting(true);

        const data = new FormData(e.target);
        const name = (data.get("name") ?? "").trim();
        const email = (data.get("email") ?? "").trim();
        const password = (data.get("password") ?? "").trim();

        try {
            // Create the Firebase account
            const credential = await createUserWithEmailAndPassword(auth, email, password);
            await updateProfile(credential.user, { displayName: name || email.split("@")[0] });

            // Get token directly from the new credential before auth state settles
            const idToken = await credential.user.getIdToken();

            // Link user to company and register role
            await acceptInvitation(token, credential.user.uid);
            await registerUserRole(credential.user.uid, "hr", idToken);

            // Send verification email — HR accounts must verify before accessing the dashboard
            try {
                await sendEmailVerification(credential.user);
            } catch {
                // Verification email is best-effort; don't block account creation
            }

            sessionStorage.setItem("myhr_role", "hr");
            localStorage.setItem("myhr_role", "hr");
            navigate("/verify-email", { replace: true });
        } catch (err) {
            const messages = {
                "auth/email-already-in-use": "An account with this email already exists. Try signing in.",
                "auth/weak-password": "Password must be at least 6 characters.",
                "auth/invalid-email": "Please enter a valid email address.",
            };
            setFormError(messages[err.code] ?? err.message ?? "Something went wrong.");
        } finally {
            setIsSubmitting(false);
        }
    };

    if (loading || validating) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
            </div>
        );
    }

    if (error) {
        const isExpired = error.includes("expired");
        return (
            <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
                <div className="absolute inset-0 gradient-hero" />

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="relative w-full max-w-sm"
                >
                    <div className="glass-strong rounded-2xl p-8 text-center space-y-5">
                        <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mx-auto">
                            {isExpired ? (
                                <Clock className="w-8 h-8 text-warning" />
                            ) : (
                                <AlertCircle className="w-8 h-8 text-destructive" />
                            )}
                        </div>
                        <h2 className="text-xl font-bold text-foreground">
                            {isExpired ? "Invitation Expired" : "Invalid Invitation"}
                        </h2>
                        <p className="text-sm text-muted-foreground">{error}</p>
                        <Button variant="hero" className="w-full h-11" asChild>
                            <Link to="/request-access">Request New Access</Link>
                        </Button>
                    </div>
                </motion.div>
            </div>
        );
    }

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
                <div className="glass-strong rounded-2xl p-8 space-y-6">
                    {/* Header */}
                    <div className="text-center space-y-2">
                        <div className="inline-flex items-center gap-2.5">
                            <div className="w-10 h-10 rounded-xl gradient-cobalt flex items-center justify-center shadow-cobalt">
                                <Brain className="w-5 h-5 text-primary-foreground" />
                            </div>
                            <span className="text-xl font-bold text-foreground">
                                My<span className="text-cobalt-light">HR</span>
                            </span>
                        </div>

                        <div className="flex items-center justify-center gap-2 mt-3">
                            <CheckCircle2 className="w-4 h-4 text-mint" />
                            <span className="text-sm font-medium text-mint-dark">Application Approved</span>
                        </div>

                        <h1 className="text-xl font-bold text-foreground">Welcome to MyHR Enterprise</h1>
                        {invitation?.companyName && (
                            <p className="text-sm text-muted-foreground">
                                Complete your account for <span className="text-foreground font-medium">{invitation.companyName}</span>
                            </p>
                        )}
                    </div>

                    {/* Sign-up form */}
                    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                        <div className="space-y-2">
                            <Label htmlFor="name">Full Name</Label>
                            <div className="relative">
                                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <Input id="name" name="name" placeholder="Jane Smith" className="pl-10 h-11" required />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <Input
                                    id="email"
                                    name="email"
                                    type="email"
                                    className="pl-10 h-11 cursor-not-allowed opacity-70"
                                    defaultValue={invitation?.email || ""}
                                    readOnly
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="password">Password</Label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <Input
                                    id="password"
                                    name="password"
                                    type="password"
                                    placeholder="••••••••"
                                    className="pl-10 h-11"
                                    minLength={6}
                                    required
                                />
                            </div>
                        </div>

                        {formError && (
                            <motion.p
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2"
                            >
                                {formError}
                            </motion.p>
                        )}

                        <Button variant="hero" className="w-full h-11" type="submit" disabled={isSubmitting}>
                            {isSubmitting ? (
                                <span className="flex items-center gap-2">
                                    <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                    Creating account…
                                </span>
                            ) : (
                                <span className="flex items-center gap-1">
                                    Create Account
                                    <ArrowRight className="w-4 h-4 ml-1" />
                                </span>
                            )}
                        </Button>
                    </form>

                    <p className="text-center text-sm text-muted-foreground">
                        Already have an account?{" "}
                        <Link to="/auth?role=hr" className="text-cobalt-light hover:text-cobalt font-medium transition-colors">
                            Sign In
                        </Link>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default AcceptInvitation;
