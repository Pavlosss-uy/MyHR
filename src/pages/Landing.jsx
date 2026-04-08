import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import Navbar from "@/components/Navbar";
import { Brain, BarChart3, Mic, Shield, Users, Zap, ArrowRight, CheckCircle2 } from "lucide-react";
import heroImage from "@/assets/hero-illustration.png";

const fadeUp = {
    hidden: { opacity: 0, y: 30 },
    visible: (i) => ({
        opacity: 1,
        y: 0,
        transition: { delay: i * 0.1, duration: 0.6, ease: [0.22, 1, 0.36, 1] },
    }),
};

const features = [
    {
        icon: Brain,
        title: "AI-Powered Questions",
        description: "Dynamic interview questions generated from job descriptions and candidate CVs using advanced AI.",
    },
    {
        icon: Mic,
        title: "Voice Interview Simulation",
        description: "Natural voice-based interviews with real-time transcription and conversational AI responses.",
    },
    {
        icon: BarChart3,
        title: "Detailed Analytics",
        description: "Comprehensive feedback reports with confidence scoring, strengths analysis, and improvement areas.",
    },
    {
        icon: Shield,
        title: "Bias-Free Evaluation",
        description: "Standardized assessment criteria ensuring fair, consistent evaluation across all candidates.",
    },
    {
        icon: Users,
        title: "Candidate Leaderboard",
        description: "Track and compare candidate performance with intuitive ranking and filtering tools.",
    },
    {
        icon: Zap,
        title: "Instant Competency Extraction",
        description: "AI automatically extracts key competencies from uploaded JDs and CVs in seconds.",
    },
];

const Landing = () => {
    const [activeTab, setActiveTab] = useState("hr");

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            {/* Hero Section */}
            <section className="relative pt-32 pb-20 overflow-hidden">
                <div className="absolute inset-0 gradient-hero opacity-[0.03]" />
                <div className="max-w-7xl mx-auto px-6">
                    <div className="grid lg:grid-cols-2 gap-16 items-center">
                        <motion.div
                            initial="hidden"
                            animate="visible"
                            className="space-y-8"
                        >
                            <motion.div custom={0} variants={fadeUp}>
                                <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-mint/10 border border-mint/20 text-mint-dark text-sm font-medium mb-4">
                                    <Zap className="w-3.5 h-3.5" />
                                    AI-Powered Interview Platform
                                </div>
                            </motion.div>

                            <motion.h1
                                custom={1}
                                variants={fadeUp}
                                className="text-5xl lg:text-6xl font-extrabold leading-[1.1] tracking-tight text-foreground"
                            >
                                Hire Smarter with{" "}
                                <span className="text-gradient-cobalt">AI Interviews</span>
                            </motion.h1>

                            <motion.p
                                custom={2}
                                variants={fadeUp}
                                className="text-lg text-muted-foreground max-w-lg leading-relaxed"
                            >
                                IntervAI transforms hiring with intelligent voice interviews, automated
                                competency analysis, and data-driven candidate evaluation.
                            </motion.p>

                            {/* HR / Candidate Toggle */}
                            <motion.div custom={3} variants={fadeUp} className="flex gap-1 p-1 bg-muted rounded-xl w-fit">
                                <button
                                    onClick={() => setActiveTab("hr")}
                                    className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === "hr"
                                            ? "bg-card text-foreground shadow-sm"
                                            : "text-muted-foreground hover:text-foreground"
                                        }`}
                                >
                                    HR Portal
                                </button>
                                <button
                                    onClick={() => setActiveTab("candidate")}
                                    className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === "candidate"
                                            ? "bg-card text-foreground shadow-sm"
                                            : "text-muted-foreground hover:text-foreground"
                                        }`}
                                >
                                    Candidate Training
                                </button>
                            </motion.div>

                            <motion.div custom={4} variants={fadeUp} className="flex gap-4">
                                {activeTab === "hr" ? (
                                    <>
                                        <Button variant="hero" size="lg" asChild>
                                            <Link to="/hr/dashboard">
                                                Open HR Dashboard
                                                <ArrowRight className="w-4 h-4 ml-1" />
                                            </Link>
                                        </Button>
                                        <Button variant="outline" size="lg" asChild>
                                            <Link to="/hr/jobs">Manage Jobs</Link>
                                        </Button>
                                    </>
                                ) : (
                                    <>
                                        <Button variant="hero" size="lg" asChild>
                                            <Link to="/candidate">
                                                Start Practicing
                                                <ArrowRight className="w-4 h-4 ml-1" />
                                            </Link>
                                        </Button>
                                        <Button variant="outline" size="lg" asChild>
                                            <Link to="/interview">Try Interview</Link>
                                        </Button>
                                    </>
                                )}
                            </motion.div>

                            <motion.div custom={5} variants={fadeUp} className="flex items-center gap-6 pt-2">
                                {["10K+ Interviews", "98% Accuracy", "50+ Companies"].map((stat) => (
                                    <div key={stat} className="flex items-center gap-1.5 text-sm text-muted-foreground">
                                        <CheckCircle2 className="w-4 h-4 text-mint" />
                                        {stat}
                                    </div>
                                ))}
                            </motion.div>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, x: 40 }}
                            animate={{ opacity: 1, scale: 1, x: 0 }}
                            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1], delay: 0.3 }}
                            className="relative hidden lg:block"
                        >
                            <div className="relative rounded-2xl overflow-hidden shadow-cobalt-lg animate-float">
                                <img
                                    src={heroImage}
                                    alt="MyHR Platform - AI-powered interview simulation"
                                    className="w-full h-auto rounded-2xl"
                                />
                                <div className="absolute inset-0 bg-gradient-to-t from-cobalt-950/30 to-transparent" />
                            </div>
                        </motion.div>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section id="features" className="py-24 bg-card/50">
                <div className="max-w-7xl mx-auto px-6">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-center mb-16"
                    >
                        <h2 className="text-3xl lg:text-4xl font-bold text-foreground mb-4">
                            Everything you need for{" "}
                            <span className="text-gradient-cobalt">smarter hiring</span>
                        </h2>
                        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                            From AI-generated questions to real-time analytics, MyHR covers every step of the interview process.
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
                                <h3 className="text-base font-semibold text-foreground mb-2">{feature.title}</h3>
                                <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="py-24">
                <div className="max-w-4xl mx-auto px-6 text-center">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="gradient-cobalt rounded-3xl p-12 lg:p-16 shadow-cobalt-lg"
                    >
                        <h2 className="text-3xl lg:text-4xl font-bold text-primary-foreground mb-4">
                            Ready to transform your hiring?
                        </h2>
                        <p className="text-cobalt-lighter text-lg mb-8 max-w-xl mx-auto">
                            Join thousands of companies using MyHR to find the best talent faster and more fairly.
                        </p>
                        <div className="flex flex-col sm:flex-row gap-4 justify-center">
                            <Button
                                size="lg"
                                className="bg-card text-primary hover:bg-card/90 shadow-lg"
                                asChild
                            >
                                <Link to="/auth?mode=signup">
                                    Start Free Trial
                                    <ArrowRight className="w-4 h-4 ml-1" />
                                </Link>
                            </Button>
                            <Button
                                size="lg"
                                variant="ghost"
                                className="text-primary-foreground border border-primary-foreground/20 hover:bg-primary-foreground/10"
                                asChild
                            >
                                <Link to="/hr/dashboard">View Demo</Link>
                            </Button>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-border py-12 bg-card">
                <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg gradient-cobalt flex items-center justify-center">
                            <Brain className="w-4 h-4 text-primary-foreground" />
                        </div>
                        <span className="font-semibold text-foreground">MyHR</span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        © 2026 MyHR. All rights reserved.
                    </p>
                </div>
            </footer>
        </div>
    );
};

export default Landing;
