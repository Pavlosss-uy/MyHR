import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Brain, Linkedin, Chrome, Mail, Lock, User, ArrowRight } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";

const Auth = () => {
    const [searchParams] = useSearchParams();
    const [isSignUp, setIsSignUp] = useState(searchParams.get("mode") === "signup");
    const navigate = useNavigate();
    const { toast } = useToast();
    const { login } = useAuth();

    const handleSubmit = (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const name = formData.get("name") || formData.get("email")?.split("@")[0] || "User";
        const email = formData.get("email") || "";

        login({ name, email, provider: "email" });

        toast({
            title: isSignUp ? "Account created!" : "Welcome back!",
            description: isSignUp ? "Your account has been created successfully." : "You have been signed in successfully.",
        });
        setTimeout(() => navigate("/candidate"), 500);
    };

    const handleGoogleAuth = () => {
        const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
        if (!clientId) {
            toast({
                title: "Google OAuth not configured",
                description: "Please set VITE_GOOGLE_CLIENT_ID in your .env file.",
                variant: "destructive",
            });
            return;
        }

        const redirectUri = `${window.location.origin}/auth/callback/google`;
        const scope = "openid email profile";
        const responseType = "token";
        const state = crypto.randomUUID();

        // Save state for CSRF verification when the callback fires
        sessionStorage.setItem("google_oauth_state", state);

        const params = new URLSearchParams({
            client_id: clientId,
            redirect_uri: redirectUri,
            response_type: responseType,
            scope,
            state,
            prompt: "select_account",
        });

        window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
    };

    const handleLinkedInAuth = () => {
        const clientId = import.meta.env.VITE_LINKEDIN_CLIENT_ID;
        if (!clientId) {
            toast({
                title: "LinkedIn OAuth not configured",
                description: "Please set VITE_LINKEDIN_CLIENT_ID in your .env file.",
                variant: "destructive",
            });
            return;
        }

        const redirectUri = `${window.location.origin}/auth/callback/linkedin`;
        const scope = "openid email";
        const responseType = "code";
        const state = crypto.randomUUID();

        // Save state for CSRF verification when the callback fires
        sessionStorage.setItem("linkedin_oauth_state", state);

        const params = new URLSearchParams({
            response_type: responseType,
            client_id: clientId,
            redirect_uri: redirectUri,
            scope,
            state,
        });

        window.location.href = `https://www.linkedin.com/oauth/v2/authorization?${params.toString()}`;
    };

    const handleSocialAuth = (provider) => {
        if (provider === "Google") {
            handleGoogleAuth();
            return;
        }
        if (provider === "LinkedIn") {
            handleLinkedInAuth();
            return;
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 gradient-hero" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(160_60%_45%/0.08),transparent_60%)]" />

            <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="relative w-full max-w-md"
            >
                {/* Glass Card */}
                <div className="glass-strong rounded-2xl p-8 space-y-6">
                    {/* Logo */}
                    <div className="text-center space-y-2">
                        <Link to="/" className="inline-flex items-center gap-2.5">
                            <div className="w-10 h-10 rounded-xl gradient-cobalt flex items-center justify-center shadow-cobalt">
                                <Brain className="w-5 h-5 text-primary-foreground" />
                            </div>
                            <span className="text-xl font-bold text-foreground">
                                Interv<span className="text-cobalt-light">AI</span>
                            </span>
                        </Link>
                        <p className="text-sm text-muted-foreground">
                            {isSignUp ? "Create your account to get started" : "Welcome back! Sign in to continue"}
                        </p>
                    </div>

                    {/* Social Auth */}
                    <div className="space-y-3">
                        <Button variant="outline" className="w-full h-11 gap-3 font-medium" onClick={() => handleSocialAuth("LinkedIn")}>
                            <Linkedin className="w-4 h-4 text-cobalt" />
                            Continue with LinkedIn
                        </Button>
                        <Button variant="outline" className="w-full h-11 gap-3 font-medium" onClick={() => handleSocialAuth("Google")}>
                            <Chrome className="w-4 h-4" />
                            Continue with Google
                        </Button>
                    </div>

                    {/* Divider */}
                    <div className="flex items-center gap-4">
                        <div className="flex-1 h-px bg-border" />
                        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">or</span>
                        <div className="flex-1 h-px bg-border" />
                    </div>

                    {/* Form */}
                    <form className="space-y-4" onSubmit={handleSubmit}>
                        {isSignUp && (
                            <div className="space-y-2">
                                <Label htmlFor="name" className="text-sm font-medium text-foreground">Full Name</Label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <Input id="name" name="name" placeholder="John Doe" className="pl-10 h-11" />
                                </div>
                            </div>
                        )}
                        <div className="space-y-2">
                            <Label htmlFor="email" className="text-sm font-medium text-foreground">Email</Label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <Input id="email" name="email" type="email" placeholder="you@company.com" className="pl-10 h-11" />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="password" className="text-sm font-medium text-foreground">Password</Label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <Input id="password" name="password" type="password" placeholder="••••••••" className="pl-10 h-11" />
                            </div>
                        </div>

                        {!isSignUp && (
                            <div className="flex justify-end">
                                <button type="button" className="text-xs text-cobalt-light hover:text-cobalt font-medium transition-colors">
                                    Forgot password?
                                </button>
                            </div>
                        )}

                        <Button variant="hero" className="w-full h-11" type="submit">
                            {isSignUp ? "Create Account" : "Sign In"}
                            <ArrowRight className="w-4 h-4 ml-1" />
                        </Button>
                    </form>

                    {/* Toggle */}
                    <p className="text-center text-sm text-muted-foreground">
                        {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
                        <button
                            onClick={() => setIsSignUp(!isSignUp)}
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
