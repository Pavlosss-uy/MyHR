import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import {
    Brain,
    ArrowRight,
    Upload,
    Mic,
    BarChart3,
    Award,
    Users,
    FileText,
    Sparkles,
    ChevronRight,
    ChevronLeft,
    CheckCircle2,
    Play,
    Shield,
    Zap,
    Target,
    BookOpen,
} from "lucide-react";

/* ─── animation variants ─── */
const fadeUp = {
    hidden: { opacity: 0, y: 30 },
    visible: (i) => ({
        opacity: 1,
        y: 0,
        transition: { delay: i * 0.12, duration: 0.6, ease: [0.22, 1, 0.36, 1] },
    }),
};

const stagger = {
    visible: { transition: { staggerChildren: 0.08 } },
};

const cardHover = {
    rest: { scale: 1, y: 0 },
    hover: { scale: 1.03, y: -4, transition: { duration: 0.25, ease: "easeOut" } },
};

/* ─── How-to steps ─── */
const howToSteps = [
    {
        icon: FileText,
        title: "Create Your Profile",
        description: "Sign up and fill out your professional profile with your skills, experience, and career goals.",
        color: "from-cobalt-light to-cobalt",
    },
    {
        icon: Upload,
        title: "Upload Your CV",
        description: "Upload your resume so our AI can analyze your competencies and tailor interview questions just for you.",
        color: "from-cobalt to-cobalt-dark",
    },
    {
        icon: Target,
        title: "Choose a Job Position",
        description: "Select a job description to practice for. Our AI extracts key competencies and maps them to interview questions.",
        color: "from-emerald-500 to-teal-600",
    },
    {
        icon: Mic,
        title: "Start AI Interview",
        description: "Enter the voice-powered interview room. Speak naturally — our AI listens, responds, and guides the conversation.",
        color: "from-teal-500 to-emerald-600",
    },
    {
        icon: BarChart3,
        title: "Get Detailed Feedback",
        description: "Receive a comprehensive report with confidence scores, strengths, improvement areas, and personalized tips.",
        color: "from-violet-500 to-purple-600",
    },
    {
        icon: Award,
        title: "Track Your Progress",
        description: "View your interview history, compare scores over time, and climb the candidate leaderboard.",
        color: "from-amber-500 to-orange-600",
    },
];

/* ─── Platform features ─── */
const platformFeatures = [
    {
        icon: Brain,
        title: "AI-Powered Questions",
        desc: "Smart questions generated from JDs and CVs",
    },
    {
        icon: Shield,
        title: "Bias-Free Evaluation",
        desc: "Standardized, fair assessment criteria",
    },
    {
        icon: Zap,
        title: "Instant Analysis",
        desc: "Real-time competency extraction",
    },
    {
        icon: Users,
        title: "HR Dashboard",
        desc: "Track candidates and manage hiring",
    },
];

/* ─── Stats ─── */
const stats = [
    { value: "10K+", label: "Interviews Completed" },
    { value: "98%", label: "Assessment Accuracy" },
    { value: "50+", label: "Partner Companies" },
    { value: "4.9★", label: "User Rating" },
];

const Welcome = () => {
    const { isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const [activeStep, setActiveStep] = useState(0);

    // If already logged in, redirect to candidate home
    useEffect(() => {
        if (isAuthenticated) {
            navigate("/candidate", { replace: true });
        }
    }, [isAuthenticated, navigate]);

    const nextStep = () => setActiveStep((s) => Math.min(s + 1, howToSteps.length - 1));
    const prevStep = () => setActiveStep((s) => Math.max(s - 1, 0));

    return (
        <div className="min-h-screen bg-background overflow-hidden">
            {/* ─── Navbar ─── */}
            <nav className="fixed top-0 left-0 right-0 z-50 glass">
                <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                        <div className="w-9 h-9 rounded-lg gradient-cobalt flex items-center justify-center shadow-cobalt">
                            <Brain className="w-5 h-5 text-primary-foreground" />
                        </div>
                        <span className="text-lg font-bold text-foreground tracking-tight">
                            Interv<span className="text-cobalt-light">AI</span>
                        </span>
                    </div>
                    <div className="flex items-center gap-3">
                        <Button variant="ghost" size="sm" asChild>
                            <Link to="/auth">Sign In</Link>
                        </Button>
                        <Button variant="hero" size="sm" asChild>
                            <Link to="/auth?mode=signup">
                                Get Started
                                <ArrowRight className="w-3.5 h-3.5 ml-1" />
                            </Link>
                        </Button>
                    </div>
                </div>
            </nav>

            {/* ─── Hero Section ─── */}
            <section className="relative pt-28 pb-20 overflow-hidden">
                {/* Background decorations */}
                <div className="absolute inset-0 gradient-hero opacity-[0.03]" />
                <div className="absolute top-20 right-0 w-[600px] h-[600px] bg-cobalt-light/5 rounded-full blur-3xl" />
                <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-mint/5 rounded-full blur-3xl" />

                <div className="max-w-7xl mx-auto px-6 relative">
                    <motion.div
                        initial="hidden"
                        animate="visible"
                        className="text-center max-w-4xl mx-auto space-y-8"
                    >
                        <motion.div custom={0} variants={fadeUp}>
                            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-mint/10 border border-mint/20 text-mint-dark text-sm font-medium">
                                <Sparkles className="w-3.5 h-3.5" />
                                Welcome to IntervAI — Your AI Interview Coach
                            </div>
                        </motion.div>

                        <motion.h1
                            custom={1}
                            variants={fadeUp}
                            className="text-5xl lg:text-7xl font-extrabold leading-[1.08] tracking-tight text-foreground"
                        >
                            Master Your Next
                            <br />
                            <span className="text-gradient-cobalt">Interview with AI</span>
                        </motion.h1>

                        <motion.p
                            custom={2}
                            variants={fadeUp}
                            className="text-lg lg:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed"
                        >
                            Practice with intelligent voice interviews, get real-time feedback,
                            and boost your confidence before the big day. Sign up to unlock
                            the full platform.
                        </motion.p>

                        <motion.div custom={3} variants={fadeUp} className="flex flex-col sm:flex-row gap-4 justify-center">
                            <Button variant="hero" size="lg" className="text-base px-8 h-13" asChild>
                                <Link to="/auth?mode=signup">
                                    <Play className="w-4 h-4 mr-2" />
                                    Start Free — Sign Up
                                </Link>
                            </Button>
                            <Button variant="outline" size="lg" className="text-base px-8 h-13" asChild>
                                <Link to="/auth">
                                    I Already Have an Account
                                </Link>
                            </Button>
                        </motion.div>

                        {/* Stats bar */}
                        <motion.div
                            custom={4}
                            variants={fadeUp}
                            className="flex flex-wrap justify-center gap-8 pt-4"
                        >
                            {stats.map((stat) => (
                                <div key={stat.label} className="text-center">
                                    <div className="text-2xl font-bold text-foreground">{stat.value}</div>
                                    <div className="text-xs text-muted-foreground mt-0.5">{stat.label}</div>
                                </div>
                            ))}
                        </motion.div>
                    </motion.div>
                </div>
            </section>

            {/* ─── How It Works Section ─── */}
            <section className="py-24 bg-card/50 relative" id="how-it-works">
                <div className="max-w-7xl mx-auto px-6">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-center mb-16"
                    >
                        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-cobalt-light/10 border border-cobalt-light/20 text-cobalt-light text-sm font-medium mb-4">
                            <BookOpen className="w-3.5 h-3.5" />
                            How It Works
                        </div>
                        <h2 className="text-3xl lg:text-5xl font-bold text-foreground mb-4">
                            Get Started in{" "}
                            <span className="text-gradient-cobalt">6 Simple Steps</span>
                        </h2>
                        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                            Follow these steps to ace your next interview with our AI-powered platform.
                        </p>
                    </motion.div>

                    {/* Step Navigator — Large Screen */}
                    <div className="hidden lg:grid lg:grid-cols-3 gap-6 mb-12">
                        {howToSteps.map((step, i) => (
                            <motion.div
                                key={step.title}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: i * 0.08 }}
                                variants={cardHover}
                                whileHover="hover"
                                className="group relative bg-card rounded-2xl p-6 border border-border hover:border-cobalt-lighter/30 hover:shadow-cobalt-lg transition-all duration-300 cursor-pointer"
                                onClick={() => setActiveStep(i)}
                            >
                                {/* Step number */}
                                <div className="absolute -top-3 -left-3 w-8 h-8 rounded-full gradient-cobalt flex items-center justify-center text-xs font-bold text-primary-foreground shadow-cobalt z-10">
                                    {i + 1}
                                </div>

                                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${step.color} flex items-center justify-center mb-4 shadow-lg`}>
                                    <step.icon className="w-6 h-6 text-white" />
                                </div>

                                <h3 className="text-lg font-semibold text-foreground mb-2">
                                    {step.title}
                                </h3>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {step.description}
                                </p>

                                {/* Connecting arrow */}
                                {i < howToSteps.length - 1 && i !== 2 && (
                                    <div className="absolute -right-3 top-1/2 -translate-y-1/2 hidden lg:block">
                                        <ChevronRight className="w-5 h-5 text-cobalt-lighter/40" />
                                    </div>
                                )}
                            </motion.div>
                        ))}
                    </div>

                    {/* Step Navigator — Mobile Carousel */}
                    <div className="lg:hidden">
                        <div className="relative bg-card rounded-2xl p-8 border border-border shadow-cobalt">
                            {/* Step number badge */}
                            <div className="absolute -top-3 left-6 flex items-center gap-2 px-3 py-1 rounded-full gradient-cobalt text-xs font-bold text-primary-foreground shadow-cobalt">
                                Step {activeStep + 1} of {howToSteps.length}
                            </div>

                            <AnimatePresence mode="wait">
                                <motion.div
                                    key={activeStep}
                                    initial={{ opacity: 0, x: 30 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -30 }}
                                    transition={{ duration: 0.3 }}
                                    className="pt-4"
                                >
                                    <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${howToSteps[activeStep].color} flex items-center justify-center mb-5 shadow-lg`}>
                                        {(() => {
                                            const Icon = howToSteps[activeStep].icon;
                                            return <Icon className="w-7 h-7 text-white" />;
                                        })()}
                                    </div>
                                    <h3 className="text-xl font-semibold text-foreground mb-3">
                                        {howToSteps[activeStep].title}
                                    </h3>
                                    <p className="text-muted-foreground leading-relaxed">
                                        {howToSteps[activeStep].description}
                                    </p>
                                </motion.div>
                            </AnimatePresence>

                            {/* Navigation */}
                            <div className="flex items-center justify-between mt-8">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={prevStep}
                                    disabled={activeStep === 0}
                                    className="gap-1"
                                >
                                    <ChevronLeft className="w-4 h-4" /> Previous
                                </Button>
                                {/* Dots */}
                                <div className="flex gap-1.5">
                                    {howToSteps.map((_, i) => (
                                        <button
                                            key={i}
                                            onClick={() => setActiveStep(i)}
                                            className={`w-2 h-2 rounded-full transition-all ${i === activeStep
                                                ? "w-6 bg-cobalt-light"
                                                : "bg-border hover:bg-muted-foreground/40"
                                                }`}
                                        />
                                    ))}
                                </div>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={nextStep}
                                    disabled={activeStep === howToSteps.length - 1}
                                    className="gap-1"
                                >
                                    Next <ChevronRight className="w-4 h-4" />
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ─── Platform Features Section ─── */}
            <section className="py-24 relative">
                <div className="max-w-7xl mx-auto px-6">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-center mb-16"
                    >
                        <h2 className="text-3xl lg:text-5xl font-bold text-foreground mb-4">
                            Why Choose{" "}
                            <span className="text-gradient-cobalt">IntervAI?</span>
                        </h2>
                        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                            Everything you need to prepare, practice, and succeed.
                        </p>
                    </motion.div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
                        {platformFeatures.map((feat, i) => (
                            <motion.div
                                key={feat.title}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: i * 0.1 }}
                                className="group text-center bg-card rounded-2xl p-8 border border-border hover:border-cobalt-lighter/30 hover:shadow-cobalt-lg transition-all duration-300"
                            >
                                <div className="w-14 h-14 rounded-2xl gradient-cobalt flex items-center justify-center mx-auto mb-5 shadow-cobalt group-hover:shadow-cobalt-lg transition-shadow">
                                    <feat.icon className="w-7 h-7 text-primary-foreground" />
                                </div>
                                <h3 className="text-base font-semibold text-foreground mb-2">{feat.title}</h3>
                                <p className="text-sm text-muted-foreground">{feat.desc}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ─── CTA Section ─── */}
            <section className="py-24 relative">
                <div className="max-w-4xl mx-auto px-6 text-center">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="gradient-cobalt rounded-3xl p-12 lg:p-16 shadow-cobalt-lg relative overflow-hidden"
                    >
                        {/* Glow decorations */}
                        <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full blur-3xl" />
                        <div className="absolute bottom-0 left-0 w-48 h-48 bg-mint/10 rounded-full blur-3xl" />

                        <div className="relative z-10">
                            <h2 className="text-3xl lg:text-4xl font-bold text-primary-foreground mb-4">
                                Ready to Ace Your Interview?
                            </h2>
                            <p className="text-cobalt-lighter text-lg mb-8 max-w-xl mx-auto">
                                Sign up now and start practicing with our AI interviewer.
                                It's free to get started — no credit card required.
                            </p>
                            <div className="flex flex-col sm:flex-row gap-4 justify-center">
                                <Button
                                    size="lg"
                                    className="bg-card text-primary hover:bg-card/90 shadow-lg text-base px-8"
                                    asChild
                                >
                                    <Link to="/auth?mode=signup">
                                        Create Free Account
                                        <ArrowRight className="w-4 h-4 ml-2" />
                                    </Link>
                                </Button>
                                <Button
                                    size="lg"
                                    variant="ghost"
                                    className="text-primary-foreground border border-primary-foreground/20 hover:bg-primary-foreground/10 text-base px-8"
                                    asChild
                                >
                                    <Link to="/auth">Sign In</Link>
                                </Button>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* ─── Footer ─── */}
            <footer className="border-t border-border py-12 bg-card">
                <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg gradient-cobalt flex items-center justify-center">
                            <Brain className="w-4 h-4 text-primary-foreground" />
                        </div>
                        <span className="font-semibold text-foreground">IntervAI</span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        © 2026 IntervAI. All rights reserved.
                    </p>
                </div>
            </footer>
        </div>
    );
};

export default Welcome;
