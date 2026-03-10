import { useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Upload, FileText, Loader2, CheckCircle2, Sparkles, X, Brain, Play } from "lucide-react";

const mockCompetencies = [
    { name: "React / TypeScript", level: "Essential" },
    { name: "System Design", level: "Essential" },
    { name: "Team Leadership", level: "Essential" },
    { name: "CI/CD Pipelines", level: "Preferred" },
    { name: "Cloud Infrastructure (AWS)", level: "Preferred" },
    { name: "GraphQL", level: "Nice to have" },
    { name: "Performance Optimization", level: "Essential" },
    { name: "Cross-functional Communication", level: "Preferred" },
];

const levelColors = {
    Essential: "bg-cobalt/10 text-cobalt border-cobalt/20",
    Preferred: "bg-mint/10 text-mint-dark border-mint/20",
    "Nice to have": "bg-muted text-muted-foreground border-border",
};

const JobManagement = () => {
    const [jdUploaded, setJdUploaded] = useState(false);
    const [cvUploaded, setCvUploaded] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [extracted, setExtracted] = useState(false);

    const handleProcess = () => {
        setProcessing(true);
        setTimeout(() => {
            setProcessing(false);
            setExtracted(true);
        }, 3000);
    };

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-5xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <h1 className="text-2xl font-bold text-foreground">Job Management</h1>
                    <p className="text-muted-foreground mt-1">Upload job descriptions and CVs to extract key competencies with AI.</p>
                </motion.div>

                <div className="grid md:grid-cols-2 gap-6 mb-8">
                    {/* JD Upload */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                    >
                        <div
                            onClick={() => setJdUploaded(true)}
                            className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${jdUploaded
                                ? "border-mint bg-mint/5"
                                : "border-border hover:border-cobalt-lighter hover:bg-muted/50"
                                }`}
                        >
                            {jdUploaded ? (
                                <div className="space-y-2">
                                    <CheckCircle2 className="w-10 h-10 text-mint mx-auto" />
                                    <p className="text-sm font-medium text-foreground">Job Description Uploaded</p>
                                    <p className="text-xs text-muted-foreground">senior_engineer_jd.pdf</p>
                                    <button onClick={(e) => { e.stopPropagation(); setJdUploaded(false); setExtracted(false); }} className="absolute top-3 right-3 text-muted-foreground hover:text-foreground">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    <div className="w-12 h-12 rounded-xl bg-primary/5 flex items-center justify-center mx-auto">
                                        <FileText className="w-6 h-6 text-primary" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-foreground">Upload Job Description</p>
                                        <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, or TXT up to 10MB</p>
                                    </div>
                                    <Button variant="outline" size="sm">
                                        <Upload className="w-3.5 h-3.5 mr-1.5" />
                                        Browse Files
                                    </Button>
                                </div>
                            )}
                        </div>
                    </motion.div>

                    {/* CV Upload */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                    >
                        <div
                            onClick={() => setCvUploaded(true)}
                            className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${cvUploaded
                                ? "border-mint bg-mint/5"
                                : "border-border hover:border-cobalt-lighter hover:bg-muted/50"
                                }`}
                        >
                            {cvUploaded ? (
                                <div className="space-y-2">
                                    <CheckCircle2 className="w-10 h-10 text-mint mx-auto" />
                                    <p className="text-sm font-medium text-foreground">CVs Uploaded</p>
                                    <p className="text-xs text-muted-foreground">3 candidate resumes</p>
                                    <button onClick={(e) => { e.stopPropagation(); setCvUploaded(false); setExtracted(false); }} className="absolute top-3 right-3 text-muted-foreground hover:text-foreground">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    <div className="w-12 h-12 rounded-xl bg-primary/5 flex items-center justify-center mx-auto">
                                        <Upload className="w-6 h-6 text-primary" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-foreground">Upload Candidate CVs</p>
                                        <p className="text-xs text-muted-foreground mt-1">Multiple files supported</p>
                                    </div>
                                    <Button variant="outline" size="sm">
                                        <Upload className="w-3.5 h-3.5 mr-1.5" />
                                        Browse Files
                                    </Button>
                                </div>
                            )}
                        </div>
                    </motion.div>
                </div>

                {/* Extract Button */}
                {jdUploaded && cvUploaded && !extracted && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="text-center mb-8"
                    >
                        <Button
                            variant="hero"
                            size="lg"
                            onClick={handleProcess}
                            disabled={processing}
                        >
                            {processing ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Extracting Competencies...
                                </>
                            ) : (
                                <>
                                    <Sparkles className="w-4 h-4 mr-2" />
                                    Extract Key Competencies with AI
                                </>
                            )}
                        </Button>
                    </motion.div>
                )}

                {/* AI Loading State */}
                <AnimatePresence>
                    {processing && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="bg-card rounded-xl border border-border p-8 text-center space-y-4"
                        >
                            <div className="w-16 h-16 rounded-2xl gradient-cobalt flex items-center justify-center mx-auto animate-pulse-glow shadow-cobalt">
                                <Brain className="w-8 h-8 text-primary-foreground" />
                            </div>
                            <div>
                                <p className="font-semibold text-foreground">AI is analyzing your documents...</p>
                                <p className="text-sm text-muted-foreground mt-1">Extracting competencies, skills, and requirements</p>
                            </div>
                            <div className="max-w-xs mx-auto">
                                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                                    <div className="h-full gradient-cobalt rounded-full animate-shimmer" style={{ width: "70%" }} />
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Extracted Competencies */}
                <AnimatePresence>
                    {extracted && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="bg-card rounded-xl border border-border shadow-sm"
                        >
                            <div className="p-5 border-b border-border flex items-center gap-3">
                                <div className="w-9 h-9 rounded-lg bg-mint/10 flex items-center justify-center">
                                    <Sparkles className="w-4 h-4 text-mint" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-foreground">Extracted Competencies</h3>
                                    <p className="text-sm text-muted-foreground">{mockCompetencies.length} competencies identified</p>
                                </div>
                            </div>
                            <div className="p-5 flex flex-wrap gap-2">
                                {mockCompetencies.map((comp, i) => (
                                    <motion.span
                                        key={comp.name}
                                        initial={{ opacity: 0, scale: 0.8 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ delay: i * 0.06 }}
                                        className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${levelColors[comp.level]}`}
                                    >
                                        {comp.name}
                                        <span className="ml-1.5 text-xs opacity-60">· {comp.level}</span>
                                    </motion.span>
                                ))}
                            </div>
                            <div className="p-5 border-t border-border flex justify-end">
                                <Button variant="hero" size="lg" asChild>
                                    <Link to="/interview">
                                        <Play className="w-4 h-4 mr-2" />
                                        Start Interviews
                                    </Link>
                                </Button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </main>
        </div>
    );
};

export default JobManagement;
