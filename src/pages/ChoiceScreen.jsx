import { useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Brain, Building2, GraduationCap, ArrowRight, ArrowLeft } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const ROLE_KEY = "myhr_role";

const choices = [
    {
        role: "hr",
        title: "Enterprise",
        subtitle: "For HR teams & companies",
        description: "Screen candidates at scale with AI-powered interviews, structured scoring, and bias-free evaluation.",
        icon: Building2,
        highlights: ["Unlimited candidate pipelines", "Team collaboration", "Analytics & reporting"],
        border: "hover:border-cobalt/60",
        iconBg: "gradient-cobalt",
    },
    {
        role: "candidate",
        title: "Personal Training",
        subtitle: "For individual candidates",
        description: "Practice real interview scenarios, get instant AI feedback, and track your improvement over time.",
        icon: GraduationCap,
        highlights: ["Unlimited mock interviews", "Voice & video practice", "Detailed feedback reports"],
        border: "hover:border-mint/60",
        iconBg: "bg-gradient-to-br from-mint to-emerald-500",
    },
];

const containerVariants = {
    hidden: {},
    show: { transition: { staggerChildren: 0.12 } },
};

const cardVariants = {
    hidden: { opacity: 0, y: 28, scale: 0.97 },
    show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.45, ease: "easeOut" } },
};

const ChoiceScreen = () => {
    const navigate = useNavigate();
    const { isAuthenticated, emailVerified } = useAuth();

    // If the user is already authenticated + verified, skip onboarding entirely
    useEffect(() => {
        if (isAuthenticated && emailVerified) {
            const savedRole = sessionStorage.getItem(ROLE_KEY) || localStorage.getItem(ROLE_KEY) || "";
            navigate(savedRole === "hr" ? "/hr/dashboard" : "/candidate", { replace: true });
        }
    }, [isAuthenticated, emailVerified, navigate]);

    const handleChoose = (role) => {
        // Persist in both storages: sessionStorage for OAuth round-trips,
        // localStorage so returning users don't see this screen again after login.
        sessionStorage.setItem(ROLE_KEY, role);
        localStorage.setItem(ROLE_KEY, role);
        navigate(`/auth?role=${role}`);
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden">
            <div className="absolute inset-0 gradient-hero" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(160_60%_45%/0.07),transparent_60%)]" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,hsl(221_83%_53%/0.07),transparent_60%)]" />

            {/* Brand header */}
            <motion.div
                initial={{ opacity: 0, y: -16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="relative mb-12 text-center"
            >
                <div className="flex items-center justify-center gap-3 mb-4">
                    <div className="w-11 h-11 rounded-xl gradient-cobalt flex items-center justify-center shadow-cobalt">
                        <Brain className="w-6 h-6 text-primary-foreground" />
                    </div>
                    <span className="text-2xl font-bold text-foreground tracking-tight">
                        My<span className="text-cobalt-light">HR</span>
                    </span>
                </div>
                <h1 className="text-3xl sm:text-4xl font-bold text-foreground leading-tight">
                    How will you use MyHR?
                </h1>
                <p className="mt-3 text-muted-foreground text-base max-w-sm mx-auto">
                    Choose the experience that fits your needs.
                </p>
            </motion.div>

            {/* Cards */}
            <motion.div
                variants={containerVariants}
                initial="hidden"
                animate="show"
                className="relative w-full max-w-3xl grid sm:grid-cols-2 gap-5"
            >
                {choices.map((choice) => {
                    const Icon = choice.icon;
                    return (
                        <motion.button
                            key={choice.role}
                            variants={cardVariants}
                            onClick={() => handleChoose(choice.role)}
                            className={`group glass-strong rounded-2xl p-7 text-left border-2 border-border transition-all duration-200 cursor-pointer ${choice.border} hover:shadow-lg hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-cobalt`}
                        >
                            <div className={`w-12 h-12 rounded-xl ${choice.iconBg} flex items-center justify-center mb-5 shadow-sm`}>
                                <Icon className="w-6 h-6 text-white" />
                            </div>
                            <h2 className="text-xl font-bold text-foreground mb-1">{choice.title}</h2>
                            <p className="text-sm font-medium text-cobalt-light mb-3">{choice.subtitle}</p>
                            <p className="text-sm text-muted-foreground leading-relaxed mb-5">{choice.description}</p>
                            <ul className="space-y-1.5 mb-6">
                                {choice.highlights.map((h) => (
                                    <li key={h} className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <span className="w-1.5 h-1.5 rounded-full bg-cobalt-light shrink-0" />
                                        {h}
                                    </li>
                                ))}
                            </ul>
                            <div className="flex items-center gap-2 text-sm font-semibold text-cobalt-light group-hover:gap-3 transition-all">
                                Get started <ArrowRight className="w-4 h-4" />
                            </div>
                        </motion.button>
                    );
                })}
            </motion.div>

            {/* Footer links */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                className="relative mt-8 flex items-center gap-5 text-xs text-muted-foreground"
            >
                <Link
                    to="/"
                    className="flex items-center gap-1 hover:text-foreground transition-colors"
                >
                    <ArrowLeft className="w-3 h-3" />
                    Back to home
                </Link>
                <span className="text-border">|</span>
                <button
                    onClick={() => navigate("/auth")}
                    className="text-cobalt-light hover:text-cobalt font-medium transition-colors"
                >
                    Already have an account? Sign in
                </button>
            </motion.div>
        </div>
    );
};

export default ChoiceScreen;
