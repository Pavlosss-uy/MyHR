import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, Building2, ArrowLeft, ArrowRight, CheckCircle2, Users, Shield, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { requestAccess } from "@/lib/interviewApi";

const COMPANY_SIZES = [
    { value: "1-10", label: "1–10 employees" },
    { value: "11-50", label: "11–50 employees" },
    { value: "51-200", label: "51–200 employees" },
    { value: "201-500", label: "201–500 employees" },
    { value: "500+", label: "500+ employees" },
];

const FREE_DOMAINS = new Set([
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "yandex.com", "zoho.com",
    "live.com", "msn.com", "me.com",
]);

const RequestAccess = () => {
    const navigate = useNavigate();
    const [submitted, setSubmitted] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [formError, setFormError] = useState("");

    const handleSubmit = async (e) => {
        e.preventDefault();
        setFormError("");

        const data = new FormData(e.target);
        const email = (data.get("contactEmail") ?? "").trim().toLowerCase();
        // NOTE: Corporate email validation disabled for testing.
        // Uncomment for production:
        // const domain = email.split("@")[1] || "";
        // if (FREE_DOMAINS.has(domain)) {
        //     setFormError("Please use your corporate email address. Free email providers are not accepted.");
        //     return;
        // }

        setIsLoading(true);

        try {
            await requestAccess({
                companyName: (data.get("companyName") ?? "").trim(),
                companySize: data.get("companySize") ?? "1-10",
                contactName: (data.get("contactName") ?? "").trim(),
                contactEmail: email,
            });
            setSubmitted(true);
        } catch (err) {
            setFormError(err.message || "Something went wrong. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
            <div className="absolute inset-0 gradient-hero" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(160_60%_45%/0.08),transparent_60%)]" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,hsl(221_83%_53%/0.06),transparent_60%)]" />

            {/* Back button */}
            <button
                onClick={() => navigate("/")}
                className="absolute top-6 left-6 flex items-center gap-1.5 text-sm text-cobalt-lighter hover:text-white transition-colors z-10"
            >
                <ArrowLeft className="w-4 h-4" />
                Back
            </button>

            <AnimatePresence mode="wait">
                {submitted ? (
                    /* ── Success screen ──────────────────────────────────── */
                    <motion.div
                        key="success"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="relative w-full max-w-md text-center"
                    >
                        <div className="glass-strong rounded-2xl p-10 space-y-6">
                            <motion.div
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={{ type: "spring", stiffness: 200, damping: 15, delay: 0.2 }}
                            >
                                <div className="w-20 h-20 rounded-full bg-mint/10 flex items-center justify-center mx-auto">
                                    <CheckCircle2 className="w-10 h-10 text-mint" />
                                </div>
                            </motion.div>

                            <div className="space-y-2">
                                <h2 className="text-2xl font-bold text-foreground">Request Submitted</h2>
                                <p className="text-muted-foreground leading-relaxed">
                                    Thank you for your interest in MyHR Enterprise. Our team will review
                                    your application and get back to you within <span className="text-foreground font-medium">24 hours</span>.
                                </p>
                            </div>

                            <div className="flex flex-col gap-3">
                                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-cobalt/5 border border-cobalt/10">
                                    <Shield className="w-5 h-5 text-cobalt-light shrink-0" />
                                    <p className="text-sm text-muted-foreground text-left">
                                        You'll receive a <span className="text-foreground font-medium">unique invitation link</span> via email once approved.
                                    </p>
                                </div>
                            </div>

                            <Button variant="outline" onClick={() => navigate("/")} className="w-full h-11">
                                Return to Home
                            </Button>
                        </div>
                    </motion.div>
                ) : (
                    /* ── Request form ────────────────────────────────────── */
                    <motion.div
                        key="form"
                        initial={{ opacity: 0, y: 20, scale: 0.98 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -10 }}
                        transition={{ duration: 0.45 }}
                        className="relative w-full max-w-md"
                    >
                        <div className="glass-strong rounded-2xl p-8 space-y-6">
                            {/* Header */}
                            <div className="text-center space-y-2">
                                <Link to="/" className="inline-flex items-center gap-2.5">
                                    <div className="w-10 h-10 rounded-xl gradient-cobalt flex items-center justify-center shadow-cobalt">
                                        <Brain className="w-5 h-5 text-primary-foreground" />
                                    </div>
                                    <span className="text-xl font-bold text-foreground">
                                        My<span className="text-cobalt-light">HR</span>
                                    </span>
                                </Link>

                                <span className="inline-block text-xs font-semibold text-cobalt bg-cobalt/10 px-2.5 py-0.5 rounded-full">
                                    Enterprise
                                </span>

                                <h1 className="text-xl font-bold text-foreground mt-2">Request Access</h1>
                                <p className="text-sm text-muted-foreground">
                                    MyHR Enterprise is available by invitation. Tell us about your company.
                                </p>
                            </div>

                            {/* Trust signals */}
                            <div className="grid grid-cols-3 gap-2 text-center">
                                {[
                                    { icon: Shield, label: "SOC 2" },
                                    { icon: Users, label: "500+ Teams" },
                                    { icon: Sparkles, label: "AI-First" },
                                ].map((s) => (
                                    <div key={s.label} className="flex flex-col items-center gap-1 px-2 py-2.5 rounded-lg bg-muted/50">
                                        <s.icon className="w-4 h-4 text-cobalt-light" />
                                        <span className="text-[10px] font-medium text-muted-foreground">{s.label}</span>
                                    </div>
                                ))}
                            </div>

                            {/* Form */}
                            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                                <div className="space-y-2">
                                    <Label htmlFor="companyName">Company Name</Label>
                                    <Input
                                        id="companyName"
                                        name="companyName"
                                        placeholder="Acme Corp"
                                        className="h-11"
                                        required
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="companySize">Company Size</Label>
                                    <select
                                        id="companySize"
                                        name="companySize"
                                        className="flex h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                        defaultValue="11-50"
                                        required
                                    >
                                        {COMPANY_SIZES.map((s) => (
                                            <option key={s.value} value={s.value}>{s.label}</option>
                                        ))}
                                    </select>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="contactName">Your Name</Label>
                                    <div className="relative">
                                        <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                        <Input
                                            id="contactName"
                                            name="contactName"
                                            placeholder="Jane Smith"
                                            className="pl-10 h-11"
                                            required
                                        />
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="contactEmail">Work Email</Label>
                                    <Input
                                        id="contactEmail"
                                        name="contactEmail"
                                        type="email"
                                        placeholder="jane@acmecorp.com"
                                        className="h-11"
                                        required
                                    />
                                    <p className="text-[11px] text-muted-foreground">
                                        Please use your corporate email. Free email providers are not accepted.
                                    </p>
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

                                <Button variant="hero" className="w-full h-11" type="submit" disabled={isLoading}>
                                    {isLoading ? (
                                        <span className="flex items-center gap-2">
                                            <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                            Submitting…
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1">
                                            Request Access
                                            <ArrowRight className="w-4 h-4 ml-1" />
                                        </span>
                                    )}
                                </Button>
                            </form>

                            <p className="text-center text-sm text-muted-foreground">
                                Looking to practice interviews?{" "}
                                <Link to="/auth?role=candidate&mode=signup" className="text-cobalt-light hover:text-cobalt font-medium transition-colors">
                                    Sign up free
                                </Link>
                            </p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default RequestAccess;
