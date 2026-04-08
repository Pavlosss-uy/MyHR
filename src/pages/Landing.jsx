import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import Navbar from "@/components/Navbar";
import {
    Brain,
    BarChart3,
    Mic,
    Shield,
    Users,
    Zap,
    ArrowRight,
    CheckCircle2,
    MessageSquare,
    TrendingUp,
    Layers,
} from "lucide-react";
import heroImage from "@/assets/hero-illustration.png";

/* ─── Animation variants ─────────────────────────────────────────────────── */
const fadeUp = {
    hidden: { opacity: 0, y: 32 },
    visible: (i) => ({
        opacity: 1,
        y: 0,
        transition: { delay: i * 0.1, duration: 0.65, ease: [0.22, 1, 0.36, 1] },
    }),
};

const fadeIn = {
    hidden: { opacity: 0, y: 20 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] },
    },
};

/* ─── Feature data ───────────────────────────────────────────────────────── */
const features = [
    {
        icon: Brain,
        title: "AI-Powered Questions",
        description:
            "Dynamic interview questions generated from job descriptions and candidate CVs using advanced AI models.",
    },
    {
        icon: Mic,
        title: "Voice Interview Simulation",
        description:
            "Natural voice-based interviews with real-time transcription and conversational AI responses.",
    },
    {
        icon: BarChart3,
        title: "Detailed Analytics",
        description:
            "Comprehensive feedback reports with confidence scoring, strengths analysis, and improvement areas.",
    },
    {
        icon: Shield,
        title: "Bias-Free Evaluation",
        description:
            "Standardized assessment criteria ensuring fair, consistent evaluation across all candidates.",
    },
    {
        icon: Users,
        title: "Candidate Leaderboard",
        description:
            "Track and compare candidate performance with intuitive ranking and filtering tools.",
    },
    {
        icon: Zap,
        title: "Instant Competency Extraction",
        description:
            "AI automatically extracts key competencies from uploaded JDs and CVs in seconds.",
    },
];

/* ─── "What we do" pillars ───────────────────────────────────────────────── */
const pillars = [
    {
        icon: MessageSquare,
        title: "AI-Driven Interview Evaluation",
        body: "Every answer is scored in real time across relevance, clarity, and technical depth using 8 custom AI models — giving you an objective, data-backed view of every candidate.",
    },
    {
        icon: TrendingUp,
        title: "Real-Time Feedback",
        body: "Candidates and recruiters receive instant feedback after each response — no waiting, no bias, no guesswork. Scores, SHAP explanations, and improvement tips are surfaced immediately.",
    },
    {
        icon: Layers,
        title: "Scalable Hiring Solutions",
        body: "Whether you are screening 5 or 5,000 candidates, MyHR adapts. Upload a JD, let AI extract competencies, and run structured interviews at scale — all from one platform.",
    },
];

/* ─── Stats ──────────────────────────────────────────────────────────────── */
const stats = [
    { value: "10K+", label: "Interviews Conducted" },
    { value: "98%",  label: "Evaluation Accuracy" },
    { value: "50+",  label: "Companies Onboarded" },
    { value: "8",    label: "Custom AI Models" },
];

/* ═══════════════════════════════════════════════════════════════════════════ */

const Landing = () => {
    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            {/* ── HERO ─────────────────────────────────────────────────────── */}
            <section className="relative pt-32 pb-24 overflow-hidden">
                {/* Ambient glows */}
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,hsl(221_83%_53%/0.07),transparent_55%)] pointer-events-none" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,hsl(160_60%_45%/0.06),transparent_55%)] pointer-events-none" />

                <div className="max-w-7xl mx-auto px-6">
                    <div className="grid lg:grid-cols-2 gap-16 items-center">

                        {/* Left — copy */}
                        <motion.div
                            initial="hidden"
                            animate="visible"
                            className="space-y-8"
                        >
                            <motion.div custom={0} variants={fadeUp}>
                                <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-mint/10 border border-mint/20 text-mint-dark text-sm font-medium">
                                    <Zap className="w-3.5 h-3.5" />
                                    AI-Powered Interview Platform
                                </div>
                            </motion.div>

                            <motion.div custom={1} variants={fadeUp} className="space-y-2">
                                <h1 className="text-6xl lg:text-7xl font-extrabold leading-[1.05] tracking-tight text-foreground">
                                    My<span className="text-gradient-cobalt">HR</span>
                                </h1>
                                <p className="text-2xl lg:text-3xl font-semibold text-muted-foreground leading-snug">
                                    Hire smarter with{" "}
                                    <span className="text-gradient-cobalt">AI interviews</span>
                                </p>
                            </motion.div>

                            <motion.p
                                custom={2}
                                variants={fadeUp}
                                className="text-lg text-muted-foreground max-w-lg leading-relaxed"
                            >
                                MyHR is an AI-powered interview system that helps companies evaluate
                                candidates efficiently and helps individuals practice real interview
                                scenarios — with intelligent, objective feedback at every step.
                            </motion.p>

                            {/* CTAs */}
                            <motion.div custom={3} variants={fadeUp} className="flex flex-wrap gap-4">
                                <Button variant="hero" size="lg" asChild>
                                    <Link to="/choose">
                                        Get Started
                                        <ArrowRight className="w-4 h-4 ml-1" />
                                    </Link>
                                </Button>
                                <Button variant="outline" size="lg" asChild>
                                    <a href="#features">See Features</a>
                                </Button>
                            </motion.div>

                            {/* Trust stats */}
                            <motion.div
                                custom={4}
                                variants={fadeUp}
                                className="flex flex-wrap items-center gap-5 pt-2"
                            >
                                {["10K+ Interviews", "98% Accuracy", "50+ Companies"].map((s) => (
                                    <div
                                        key={s}
                                        className="flex items-center gap-1.5 text-sm text-muted-foreground"
                                    >
                                        <CheckCircle2 className="w-4 h-4 text-mint shrink-0" />
                                        {s}
                                    </div>
                                ))}
                            </motion.div>
                        </motion.div>

                        {/* Right — illustration */}
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, x: 40 }}
                            animate={{ opacity: 1, scale: 1, x: 0 }}
                            transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1], delay: 0.3 }}
                            className="relative hidden lg:block"
                        >
                            <div className="relative rounded-2xl overflow-hidden shadow-cobalt-lg animate-float">
                                <img
                                    src={heroImage}
                                    alt="MyHR Platform – AI-powered interview simulation"
                                    className="w-full h-auto rounded-2xl"
                                />
                                <div className="absolute inset-0 bg-gradient-to-t from-cobalt-950/30 to-transparent" />
                            </div>
                        </motion.div>
                    </div>
                </div>
            </section>

            {/* ── STATS STRIP ──────────────────────────────────────────────── */}
            <section className="border-y border-border bg-card/60 py-10">
                <div className="max-w-5xl mx-auto px-6">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
                        {stats.map((s, i) => (
                            <motion.div
                                key={s.label}
                                initial={{ opacity: 0, y: 16 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: i * 0.07 }}
                            >
                                <p className="text-3xl font-extrabold text-gradient-cobalt">{s.value}</p>
                                <p className="text-sm text-muted-foreground mt-1">{s.label}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── WHO WE ARE / WHAT WE DO ──────────────────────────────────── */}
            <section className="py-24 bg-background">
                <div className="max-w-7xl mx-auto px-6">
                    <motion.div
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true }}
                        variants={fadeIn}
                        className="text-center mb-16 max-w-2xl mx-auto"
                    >
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cobalt/10 border border-cobalt/20 text-cobalt-lighter text-xs font-semibold uppercase tracking-widest mb-4">
                            What We Do
                        </div>
                        <h2 className="text-3xl lg:text-4xl font-bold text-foreground mb-4">
                            Intelligent hiring,{" "}
                            <span className="text-gradient-cobalt">end to end</span>
                        </h2>
                        <p className="text-muted-foreground text-lg leading-relaxed">
                            From automated question generation to SHAP-powered score explanations,
                            MyHR replaces guesswork with data — for both recruiters and candidates.
                        </p>
                    </motion.div>

                    <div className="grid md:grid-cols-3 gap-8">
                        {pillars.map((p, i) => (
                            <motion.div
                                key={p.title}
                                initial={{ opacity: 0, y: 24 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: i * 0.1, duration: 0.55 }}
                                className="group relative bg-card rounded-2xl border border-border p-8 hover:border-cobalt-lighter/30 hover:shadow-cobalt transition-all duration-300"
                            >
                                {/* Accent glow on hover */}
                                <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-cobalt/0 to-cobalt/0 group-hover:from-cobalt/5 group-hover:to-transparent transition-all duration-300 pointer-events-none" />

                                <div className="w-12 h-12 rounded-xl gradient-cobalt flex items-center justify-center mb-5 shadow-cobalt">
                                    <p.icon className="w-5 h-5 text-primary-foreground" />
                                </div>
                                <h3 className="text-lg font-bold text-foreground mb-3">{p.title}</h3>
                                <p className="text-sm text-muted-foreground leading-relaxed">{p.body}</p>
                            </motion.div>
                        ))}
                    </div>

                    {/* Bullet highlights */}
                    <motion.div
                        initial={{ opacity: 0, y: 16 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.3 }}
                        className="mt-12 flex flex-wrap justify-center gap-4"
                    >
                        {[
                            "8 custom PyTorch models",
                            "Adaptive difficulty engine (PPO)",
                            "Hybrid BM25 + semantic retrieval",
                            "SHAP explainability on every score",
                            "Fairness-audited evaluation",
                        ].map((item) => (
                            <div
                                key={item}
                                className="flex items-center gap-2 px-4 py-2 rounded-full bg-card border border-border text-sm text-muted-foreground"
                            >
                                <CheckCircle2 className="w-3.5 h-3.5 text-mint shrink-0" />
                                {item}
                            </div>
                        ))}
                    </motion.div>
                </div>
            </section>

            {/* ── FEATURES ─────────────────────────────────────────────────── */}
            <section id="features" className="py-24 bg-card/50">
                <div className="max-w-7xl mx-auto px-6">
                    <motion.div
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true }}
                        variants={fadeIn}
                        className="text-center mb-16"
                    >
                        <h2 className="text-3xl lg:text-4xl font-bold text-foreground mb-4">
                            Everything you need for{" "}
                            <span className="text-gradient-cobalt">smarter hiring</span>
                        </h2>
                        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                            From AI-generated questions to real-time analytics, MyHR covers every
                            step of the interview process.
                        </p>
                    </motion.div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {features.map((feature, i) => (
                            <motion.div
                                key={feature.title}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: i * 0.08 }}
                                className="group bg-card rounded-xl p-6 border border-border hover:border-cobalt-lighter/30 hover:shadow-cobalt transition-all duration-300"
                            >
                                <div className="w-11 h-11 rounded-lg bg-primary/5 flex items-center justify-center mb-4 group-hover:bg-primary/10 transition-colors">
                                    <feature.icon className="w-5 h-5 text-primary" />
                                </div>
                                <h3 className="text-base font-semibold text-foreground mb-2">
                                    {feature.title}
                                </h3>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {feature.description}
                                </p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── CTA BANNER ───────────────────────────────────────────────── */}
            <section className="py-24">
                <div className="max-w-4xl mx-auto px-6 text-center">
                    <motion.div
                        initial={{ opacity: 0, y: 24 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="gradient-cobalt rounded-3xl p-12 lg:p-16 shadow-cobalt-lg relative overflow-hidden"
                    >
                        {/* Inner glow */}
                        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,hsl(160_60%_45%/0.15),transparent_60%)] pointer-events-none" />

                        <h2 className="relative text-3xl lg:text-4xl font-bold text-primary-foreground mb-4">
                            Ready to transform your hiring?
                        </h2>
                        <p className="relative text-cobalt-lighter text-lg mb-8 max-w-xl mx-auto">
                            Join thousands of companies and candidates using MyHR to find the best
                            talent faster and more fairly.
                        </p>
                        <div className="relative flex flex-col sm:flex-row gap-4 justify-center">
                            <Button
                                size="lg"
                                className="bg-card text-primary hover:bg-card/90 shadow-lg font-semibold"
                                asChild
                            >
                                <Link to="/choose">
                                    Get Started Free
                                    <ArrowRight className="w-4 h-4 ml-1" />
                                </Link>
                            </Button>
                            <Button
                                size="lg"
                                variant="ghost"
                                className="text-primary-foreground border border-primary-foreground/20 hover:bg-primary-foreground/10"
                                asChild
                            >
                                <a href="#features">Learn More</a>
                            </Button>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* ── FOOTER ───────────────────────────────────────────────────── */}
            <footer className="border-t border-border py-12 bg-card">
                <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg gradient-cobalt flex items-center justify-center">
                            <Brain className="w-4 h-4 text-primary-foreground" />
                        </div>
                        <span className="font-bold text-foreground text-lg">
                            My<span className="text-gradient-cobalt">HR</span>
                        </span>
                    </div>

                    <nav className="flex flex-wrap gap-6 text-sm text-muted-foreground">
                        <a href="#features" className="hover:text-foreground transition-colors">Features</a>
                        <Link to="/choose" className="hover:text-foreground transition-colors">Get Started</Link>
                        <Link to="/auth"   className="hover:text-foreground transition-colors">Sign In</Link>
                    </nav>

                    <p className="text-sm text-muted-foreground">
                        © 2026 MyHR. All rights reserved.
                    </p>
                </div>
            </footer>
        </div>
    );
};

export default Landing;
