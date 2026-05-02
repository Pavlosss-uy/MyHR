import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
    createUserWithEmailAndPassword,
    signInWithEmailAndPassword,
    signInWithPopup,
    signOut,
    sendEmailVerification,
    sendPasswordResetEmail,
    GoogleAuthProvider,
    EmailAuthProvider,
    linkWithCredential,
} from "firebase/auth";
import { auth, googleProvider } from "@/lib/firebase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Brain, Chrome, Mail, Lock, User, ArrowRight, ArrowLeft, Eye, EyeOff, KeyRound } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { ADMIN_EMAIL, ADMIN_PASSWORD } from "@/contexts/AuthContext";
import { registerUserRole, getUserRole } from "@/lib/interviewApi";

const ROLE_KEY = "myhr_role";

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
    const { isAuthenticated, emailVerified, isAdmin } = useAuth();

    const [isSignUp,           setIsSignUp]           = useState(searchParams.get("mode") === "signup");
    const [isForgotPassword,   setIsForgotPassword]   = useState(false);
    const [showPassword,       setShowPassword]        = useState(false);
    const [isLoading,          setIsLoading]           = useState(false);
    const [formError,          setFormError]           = useState("");
    const [formSuccess,        setFormSuccess]         = useState("");
    // Google+Email account linking
    const [pendingGoogleCred,  setPendingGoogleCred]   = useState(null);
    const [linkEmail,          setLinkEmail]           = useState("");
    const [linkPassword,       setLinkPassword]        = useState("");
    const [isLinking,          setIsLinking]           = useState(false);

    // Prevents the auto-redirect useEffect from firing while handleSubmit is
    // mid-flight doing a role check — otherwise Firebase auth state update
    // triggers navigation before getUserRole returns.
    const skipAutoRedirect = useRef(false);

    // Role from URL param or previously persisted session
    const role = searchParams.get("role") || sessionStorage.getItem("myhr_role") || "";
    const copy = ROLE_COPY[role] ?? {};

    // Persist role across potential redirects
    useEffect(() => {
        if (role) sessionStorage.setItem("myhr_role", role);
    }, [role]);

    // If already authenticated and verified, send them home.
    // Suppressed while handleSubmit is doing an async role check.
    useEffect(() => {
        if (skipAutoRedirect.current) return;
        if (isAuthenticated && emailVerified) {
            const dest = location.state?.from?.pathname ??
                (isAdmin ? "/admin/requests" : role === "hr" ? "/hr/dashboard" : "/candidate");
            navigate(dest, { replace: true });
        }
    }, [isAuthenticated, emailVerified]); // eslint-disable-line react-hooks/exhaustive-deps

    const redirectAfterAuth = () => {
        const dest = location.state?.from?.pathname ??
            (isAdmin ? "/admin/requests" : role === "hr" ? "/hr/dashboard" : "/candidate");
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
                const { updateProfile } = await import("firebase/auth");
                await updateProfile(credential.user, { displayName: name || email.split("@")[0] });

                // Dispatch the verification email before any other async work.
                // Doing it after registerUserRole was the bug: if that call failed
                // (or a route guard redirected first), the email was never sent.
                await sendEmailVerification(credential.user);

                // Register role after the email is out — a backend failure here
                // won't prevent the user from verifying their address.
                if (role) {
                    try {
                        await registerUserRole(credential.user.uid, role);
                    } catch {
                        // Non-fatal: the account exists and the email was sent.
                        // Role registration can be retried on next sign-in.
                    }
                }

                navigate("/verify-email", { replace: true });
            } else {
                // ── SIGN-IN LOGIC ────────────────────────────────────────
                const normalizedEmail = email.toLowerCase();

                // ▸ Super Admin fast-path
                if (normalizedEmail === ADMIN_EMAIL) {
                    // Admin must NOT sign in through the candidate/training portal
                    if (role === "candidate") {
                        setFormError("Invalid email or password.");
                        setIsLoading(false);
                        return;
                    }
                    // Verify the hardcoded admin password before touching Firebase
                    if (password !== ADMIN_PASSWORD) {
                        setFormError("Invalid email or password.");
                        setIsLoading(false);
                        return;
                    }
                    // Credentials match — create Firebase session
                    await signInWithEmailAndPassword(auth, email, password);
                    sessionStorage.setItem(ROLE_KEY, "hr");
                    localStorage.setItem(ROLE_KEY, "hr");
                    navigate("/admin/requests", { replace: true });
                    return;

                // ▸ Regular user — portal-match interception
                } else {
                    // Block the auto-redirect useEffect until we've confirmed
                    // the role matches the portal the user signed in from.
                    skipAutoRedirect.current = true;

                    // Sign in first (we need the uid for role lookup)
                    const credential = await signInWithEmailAndPassword(auth, email, password);

                    if (role) {
                        const roleData = await getUserRole(credential.user.uid);
                        const storedRole = roleData?.role;

                        if (storedRole && storedRole !== role) {
                            // Mismatch — tear down the session immediately
                            await signOut(auth);
                            skipAutoRedirect.current = false;
                            setFormError("Invalid email or password.");
                            setIsLoading(false);
                            return;
                        }
                        if (storedRole) {
                            sessionStorage.setItem(ROLE_KEY, storedRole);
                            localStorage.setItem(ROLE_KEY, storedRole);
                        }
                    }
                    // Role confirmed — navigate explicitly rather than relying on useEffect
                    skipAutoRedirect.current = false;
                    redirectAfterAuth();
                }
            }
        } catch (err) {
            skipAutoRedirect.current = false;
            const msg = getErrorMessage(err.code);
            if (msg) setFormError(msg);
        } finally {
            setIsLoading(false);
        }
    };

    // ── Forgot Password ───────────────────────────────────────────────────────
    const handleForgotPassword = async (e) => {
        e.preventDefault();
        setFormError("");
        setFormSuccess("");
        setIsLoading(true);

        const data  = new FormData(e.target);
        const email = (data.get("resetEmail") ?? "").trim();

        try {
            await sendPasswordResetEmail(auth, email);
            setFormSuccess("Password reset email sent! Check your inbox (and spam folder).");
        } catch (err) {
            const map = {
                "auth/user-not-found":   "No account found with this email.",
                "auth/invalid-email":    "Please enter a valid email address.",
                "auth/too-many-requests":"Too many attempts. Please wait a moment.",
            };
            setFormError(map[err.code] ?? "Something went wrong. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    // ── Google OAuth ──────────────────────────────────────────────────────────
    const handleGoogleSignIn = async () => {
        setFormError("");
        setIsLoading(true);
        try {
            const result = await signInWithPopup(auth, googleProvider);
            const googleEmail = result.user?.email?.toLowerCase();

            // ▸ Admin via Google — auto-assign hr role, block on candidate portal
            if (googleEmail === ADMIN_EMAIL) {
                if (role === "candidate") {
                    await signOut(auth);
                    setFormError("Invalid email or password.");
                    setIsLoading(false);
                    return;
                }
                sessionStorage.setItem(ROLE_KEY, "hr");
                localStorage.setItem(ROLE_KEY, "hr");
                // Link email/password provider so admin can also sign in with credentials.
                // Silently skipped if already linked (auth/provider-already-linked).
                try {
                    const emailCred = EmailAuthProvider.credential(ADMIN_EMAIL, ADMIN_PASSWORD);
                    await linkWithCredential(result.user, emailCred);
                } catch { /* non-fatal */ }
                navigate("/admin/requests", { replace: true });
                return;
            }

            // ▸ Regular Google user — portal-match check
            if (role) {
                const roleData = await getUserRole(result.user.uid);
                const storedRole = roleData?.role;
                if (storedRole && storedRole !== role) {
                    await signOut(auth);
                    setFormError("Invalid email or password.");
                    setIsLoading(false);
                    return;
                }
                if (storedRole) {
                    sessionStorage.setItem(ROLE_KEY, storedRole);
                    localStorage.setItem(ROLE_KEY, storedRole);
                }
            }

            redirectAfterAuth();
        } catch (err) {
            if (err.code === "auth/account-exists-with-different-credential") {
                // Email already has a password account — offer linking
                const googleCredential = GoogleAuthProvider.credentialFromError(err);
                const email = err.customData?.email ?? "";
                setPendingGoogleCred(googleCredential);
                setLinkEmail(email);
                setFormError(
                    `An account already exists for ${email}. Enter your password below to link your Google account.`
                );
            } else {
                const msg = getErrorMessage(err.code);
                if (msg) {
                    setFormError(msg);
                    toast({ title: "Google sign-in failed", description: msg, variant: "destructive" });
                }
            }
        } finally {
            setIsLoading(false);
        }
    };

    // ── Account linking (Google + existing email/password) ────────────────────
    const handleLinkAccount = async (e) => {
        e.preventDefault();
        setFormError("");
        setIsLinking(true);
        try {
            const userCred = await signInWithEmailAndPassword(auth, linkEmail, linkPassword);
            await linkWithCredential(userCred.user, pendingGoogleCred);
            setPendingGoogleCred(null);
            setLinkEmail("");
            setLinkPassword("");
            toast({ title: "Accounts linked!", description: "You can now sign in with Google or email." });
            redirectAfterAuth();
        } catch (err) {
            const map = {
                "auth/wrong-password":   "Incorrect password.",
                "auth/too-many-requests": "Too many attempts. Please wait.",
            };
            setFormError(map[err.code] ?? "Linking failed. Please try again.");
        } finally {
            setIsLinking(false);
        }
    };

    // ── Account-linking overlay (Google + email collision) ────────────────────
    const LinkingOverlay = () => (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-sm">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-strong rounded-2xl p-8 w-full max-w-sm space-y-5"
            >
                <div className="text-center space-y-1">
                    <KeyRound className="w-8 h-8 text-cobalt mx-auto mb-2" />
                    <h2 className="text-lg font-bold text-foreground">Link your Google account</h2>
                    <p className="text-sm text-muted-foreground">
                        An account already exists for <span className="font-medium text-foreground">{linkEmail}</span>.
                        Enter your password to link Google sign-in.
                    </p>
                </div>

                <form onSubmit={handleLinkAccount} className="space-y-4">
                    <div className="space-y-2">
                        <Label>Password for {linkEmail}</Label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                type="password"
                                value={linkPassword}
                                onChange={(e) => setLinkPassword(e.target.value)}
                                placeholder="••••••••"
                                className="pl-10 h-11"
                                autoComplete="current-password"
                                required
                            />
                        </div>
                    </div>

                    {formError && (
                        <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
                            {formError}
                        </p>
                    )}

                    <div className="flex gap-3">
                        <Button
                            type="button"
                            variant="outline"
                            className="flex-1 h-10"
                            onClick={() => { setPendingGoogleCred(null); setFormError(""); }}
                        >
                            Cancel
                        </Button>
                        <Button variant="hero" type="submit" disabled={isLinking} className="flex-1 h-10">
                            {isLinking ? (
                                <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                            ) : "Link Account"}
                        </Button>
                    </div>
                </form>
            </motion.div>
        </div>
    );

    return (
        <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
            <div className="absolute inset-0 gradient-hero" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(160_60%_45%/0.08),transparent_60%)]" />

            {/* Account linking overlay */}
            {pendingGoogleCred && <LinkingOverlay />}

            {/* Back button */}
            <button
                onClick={() => {
                    if (isForgotPassword) { setIsForgotPassword(false); setFormError(""); setFormSuccess(""); }
                    else navigate("/");
                }}
                className="absolute top-6 left-6 flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
                <ArrowLeft className="w-4 h-4" />
                {isForgotPassword ? "Back to Sign In" : "Back"}
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

                        {!isForgotPassword && copy.badge && (
                            <span className="inline-block text-xs font-semibold text-cobalt bg-cobalt/10 px-2.5 py-0.5 rounded-full">
                                {copy.badge}
                            </span>
                        )}

                        <p className="text-sm text-muted-foreground">
                            {isForgotPassword
                                ? "Enter your email and we'll send a reset link"
                                : copy.subtitle ?? (isSignUp ? "Create your account to get started" : "Welcome back! Sign in to continue")}
                        </p>
                    </div>

                    {/* ── Forgot Password form ──────────────────────────────── */}
                    <AnimatePresence mode="wait">
                    {isForgotPassword ? (
                        <motion.form
                            key="forgot"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="space-y-4"
                            onSubmit={handleForgotPassword}
                            noValidate
                        >
                            <div className="space-y-2">
                                <Label htmlFor="resetEmail">Email</Label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <Input
                                        id="resetEmail"
                                        name="resetEmail"
                                        type="email"
                                        placeholder="you@company.com"
                                        className="pl-10 h-11"
                                        autoComplete="email"
                                        required
                                    />
                                </div>
                            </div>

                            {formError && (
                                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                    className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
                                    {formError}
                                </motion.p>
                            )}
                            {formSuccess && (
                                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                    className="text-sm text-mint bg-mint/10 rounded-lg px-3 py-2">
                                    {formSuccess}
                                </motion.p>
                            )}

                            <Button variant="hero" className="w-full h-11" type="submit" disabled={isLoading}>
                                {isLoading ? (
                                    <span className="flex items-center gap-2">
                                        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                        Sending…
                                    </span>
                                ) : (
                                    <span className="flex items-center gap-1">
                                        Send Reset Link
                                        <ArrowRight className="w-4 h-4 ml-1" />
                                    </span>
                                )}
                            </Button>

                            <p className="text-center text-sm text-muted-foreground">
                                Remember your password?{" "}
                                <button
                                    type="button"
                                    onClick={() => { setIsForgotPassword(false); setFormError(""); setFormSuccess(""); }}
                                    className="text-cobalt-light hover:text-cobalt font-medium transition-colors"
                                >
                                    Sign In
                                </button>
                            </p>
                        </motion.form>
                    ) : (
                        /* ── Normal sign-in / sign-up ──────────────────────── */
                        <motion.div
                            key="main"
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 20 }}
                            className="space-y-6"
                        >
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
                                    <div className="flex items-center justify-between">
                                        <Label htmlFor="password">Password</Label>
                                        {!isSignUp && (
                                            <button
                                                type="button"
                                                onClick={() => { setIsForgotPassword(true); setFormError(""); setFormSuccess(""); }}
                                                className="text-xs text-cobalt-light hover:text-cobalt transition-colors"
                                            >
                                                Forgot password?
                                            </button>
                                        )}
                                    </div>
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
                                    onClick={() => { setIsSignUp((v) => !v); setFormError(""); setFormSuccess(""); }}
                                    className="text-cobalt-light hover:text-cobalt font-medium transition-colors"
                                >
                                    {isSignUp ? "Sign In" : "Sign Up"}
                                </button>
                            </p>
                        </motion.div>
                    )}
                    </AnimatePresence>
                </div>
            </motion.div>
        </div>
    );
};

export default Auth;
