import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
    createUserWithEmailAndPassword,
    signInWithEmailAndPassword,
    signInWithPopup,
    sendEmailVerification,
} from "firebase/auth";
import { auth, googleProvider } from "@/lib/firebase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Brain, Chrome, Mail, Lock, User, ArrowRight, ArrowLeft, Eye, EyeOff } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";

// Human-readable Firebase error messages
const FIREBASE_ERRORS = {
    "auth/email-already-in-use":    "An account with this email already exists.",
    "auth/invalid-email":           "Please enter a valid email address.",
    "auth/weak-password":           "Password must be at least 6 characters.",
    "auth/user-not-found":          "No account found with this email.",
    "auth/wrong-password":          "Incorrect password. Please try again.",
    "auth/invalid-credential":      "Incorrect email or password.",
    "auth/too-many-requests":       "Too many attempts. Please wait a moment and try again.",
    "auth/network-request-failed":  "Network error. Check your connection and try again.",
    "auth/popup-closed-by-user":    "Sign-in popup was closed. Please try again.",
    "auth/cancelled-popup-request": null, // silent — user just opened another popup
};

const getErrorMessage = (code) =>
    FIREBASE_ERRORS[code] ?? "Something went wrong. Please try again.";

const ROLE_COPY = {
    hr:        { badge: "Enterprise",        subtitle: "Sign in to manage your team's interviews" },
    candidate: { badge: "Personal Training", subtitle: "Sign in to start practising" },
};

const Auth = () => {
    const [searchParams]  = useSearchParams();
    const navigate        = useNavigate();
    const location        = useLocation();
    const { toast }       = useToast();
    const { isAuthenticated, emailVerified } = useAuth();

    const [isSignUp,      setIsSignUp]      = useState(searchParams.get("mode") === "signup");
    const [showPassword,  setShowPassword]  = useState(false);
    const [isLoading,     setIsLoading]     = useState(false);
    const [formError,     setFormError]     = useState("");

    // Role from URL param or previously persisted session
    const role = searchParams.get("role") || sessionStorage.getItem("myhr_role") || "";
    const copy = ROLE_COPY[role] ?? {};

    // Persist role across potential redirects
    useEffect(() => {
        if (role) sessionStorage.setItem("myhr_role", role);
    }, [role]);

    // If already authenticated and verified, send them home
    useEffect(() => {
        if (isAuthenticated && emailVerified) {
            const dest = location.state?.from?.pathname ?? (role === "hr" ? "/hr/dashboard" : "/candidate");
            navigate(dest, { replace: true });
        }
    }, [isAuthenticated, emailVerified]); // eslint-disable-line react-hooks/exhaustive-deps

    const redirectAfterAuth = () => {
        const dest = location.state?.from?.pathname ?? (role === "hr" ? "/hr/dashboard" : "/candidate");
        navigate(dest, { replace: true });
    };

    // ── Email / Password ──────────────────────────────────────────────────────
    const handleSubmit = async (e) => {
        e.preventDefault();
        setFormError("");
        setIsLoading(true);

        const data     = new FormData(e.target);
        const name     = (data.get("name")     ?? "").trim();
        const email    = (data.get("email")    ?? "").trim();
        const password = (data.get("password") ?? "").trim();

        try {
            if (isSignUp) {
                const credential = await createUserWithEmailAndPassword(auth, email, password);
                // Set display name immediately
                const { updateProfile } = await import("firebase/auth");
                await updateProfile(credential.user, { displayName: name || email.split("@")[0] });
                await sendEmailVerification(credential.user);
                navigate("/verify-email", { replace: true });
            } else {
                await signInWithEmailAndPassword(auth, email, password);
                // onAuthStateChanged in AuthContext will update `user`;
                // the useEffect above will redirect once isAuthenticated flips.
            }
        } catch (err) {
            const msg = getErrorMessage(err.code);
            if (msg) setFormError(msg);
        } finally {
            setIsLoading(false);
        }
    };

    // ── Google OAuth ──────────────────────────────────────────────────────────
    const handleGoogleSignIn = async () => {
        setFormError("");
        setIsLoading(true);
        try {
            await signInWithPopup(auth, googleProvider);
            // Google accounts are pre-verified; redirect immediately
            redirectAfterAuth();
        } catch (err) {
            const msg = getErrorMessage(err.code);
            if (msg) {
                setFormError(msg);
                toast({ title: "Google sign-in failed", description: msg, variant: "destructive" });
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
            <div className="absolute inset-0 gradient-hero" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(160_60%_45%/0.08),transparent_60%)]" />

            {/* Back button */}
            <button
                onClick={() => navigate("/")}
                className="absolute top-6 left-6 flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
                <ArrowLeft className="w-4 h-4" />
                Back
            </button>

            <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.45 }}
                className="relative w-full max-w-md"
            >
                <div className="glass-strong rounded-2xl p-8 space-y-6">
                    {/* Logo + role badge */}
                    <div className="text-center space-y-2">
                        <Link to="/" className="inline-flex items-center gap-2.5">
                            <div className="w-10 h-10 rounded-xl gradient-cobalt flex items-center justify-center shadow-cobalt">
                                <Brain className="w-5 h-5 text-primary-foreground" />
                            </div>
                            <span className="text-xl font-bold text-foreground">
                                My<span className="text-cobalt-light">HR</span>
                            </span>
                        </Link>

                        {copy.badge && (
                            <span className="inline-block text-xs font-semibold text-cobalt bg-cobalt/10 px-2.5 py-0.5 rounded-full">
                                {copy.badge}
                            </span>
                        )}

                        <p className="text-sm text-muted-foreground">
                            {copy.subtitle ?? (isSignUp ? "Create your account to get started" : "Welcome back! Sign in to continue")}
                        </p>
                    </div>

                    {/* Google */}
                    <Button
                        variant="outline"
                        className="w-full h-11 gap-3 font-medium"
                        onClick={handleGoogleSignIn}
                        disabled={isLoading}
                    >
                        <Chrome className="w-4 h-4" />
                        Continue with Google
                    </Button>

                    <div className="flex items-center gap-4">
                        <div className="flex-1 h-px bg-border" />
                        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">or</span>
                        <div className="flex-1 h-px bg-border" />
                    </div>

                    {/* Email / password form */}
                    <form className="space-y-4" onSubmit={handleSubmit} noValidate>
                        {isSignUp && (
                            <div className="space-y-2">
                                <Label htmlFor="name">Full Name</Label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <Input id="name" name="name" placeholder="Jane Smith" className="pl-10 h-11" required />
                                </div>
                            </div>
                        )}

                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <Input
                                    id="email"
                                    name="email"
                                    type="email"
                                    placeholder="you@company.com"
                                    className="pl-10 h-11"
                                    autoComplete="email"
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
                                    type={showPassword ? "text" : "password"}
                                    placeholder="••••••••"
                                    className="pl-10 pr-10 h-11"
                                    autoComplete={isSignUp ? "new-password" : "current-password"}
                                    required
                                    minLength={6}
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword((p) => !p)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                    tabIndex={-1}
                                >
                                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        {/* Error banner */}
                        {formError && (
                            <motion.p
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2"
                            >
                                {formError}
                            </motion.p>
                        )}

                        <Button variant="hero" className="w-full h-11" type="submit" disabled={isLoading}>
                            {isLoading ? (
                                <span className="flex items-center gap-2">
                                    <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                    {isSignUp ? "Creating account…" : "Signing in…"}
                                </span>
                            ) : (
                                <span className="flex items-center gap-1">
                                    {isSignUp ? "Create Account" : "Sign In"}
                                    <ArrowRight className="w-4 h-4 ml-1" />
                                </span>
                            )}
                        </Button>
                    </form>

                    {/* Toggle sign-in ↔ sign-up */}
                    <p className="text-center text-sm text-muted-foreground">
                        {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
                        <button
                            onClick={() => { setIsSignUp((v) => !v); setFormError(""); }}
                            className="text-cobalt-light hover:text-cobalt font-medium transition-colors"
                        >
                            {isSignUp ? "Sign In" : "Sign Up"}
                        </button>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default Auth;
