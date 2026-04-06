import { useState } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, ArrowRight, Play, Star, Search, Filter } from "lucide-react";

const allInterviews = [
    { id: 1, role: "Senior Frontend Developer", company: "TechCorp", date: "Feb 5, 2026", score: 88, duration: "22 min" },
    { id: 2, role: "Full Stack Engineer", company: "StartupXYZ", date: "Feb 3, 2026", score: 76, duration: "18 min" },
    { id: 3, role: "React Developer", company: "InnovateCo", date: "Jan 30, 2026", score: 92, duration: "25 min" },
    { id: 4, role: "Product Manager", company: "BigCorp", date: "Jan 28, 2026", score: 71, duration: "20 min" },
    { id: 5, role: "Software Engineer", company: "TechGiant", date: "Jan 25, 2026", score: 85, duration: "24 min" },
    { id: 6, role: "Backend Developer", company: "DataFlow", date: "Jan 22, 2026", score: 79, duration: "21 min" },
    { id: 7, role: "DevOps Engineer", company: "CloudScale", date: "Jan 18, 2026", score: 82, duration: "19 min" },
    { id: 8, role: "UI Engineer", company: "DesignFirst", date: "Jan 15, 2026", score: 90, duration: "23 min" },
    { id: 9, role: "Systems Architect", company: "EnterpriseX", date: "Jan 10, 2026", score: 67, duration: "28 min" },
    { id: 10, role: "Frontend Developer", company: "WebAgency", date: "Jan 5, 2026", score: 73, duration: "17 min" },
];

const InterviewHistory = () => {
    const [searchQuery, setSearchQuery] = useState("");
    const [scoreFilter, setScoreFilter] = useState("all");

    const filteredInterviews = allInterviews.filter((interview) => {
        const matchesSearch =
            interview.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
            interview.company.toLowerCase().includes(searchQuery.toLowerCase());

        let matchesScore = true;
        if (scoreFilter === "excellent") matchesScore = interview.score >= 85;
        else if (scoreFilter === "good") matchesScore = interview.score >= 70 && interview.score < 85;
        else if (scoreFilter === "needswork") matchesScore = interview.score < 70;

        return matchesSearch && matchesScore;
    });

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-4xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
                        <Link to="/candidate">
                            <ArrowLeft className="w-4 h-4 mr-1" />
                            Back to Home
                        </Link>
                    </Button>
                    <h1 className="text-2xl font-bold text-foreground">Interview History</h1>
                    <p className="text-muted-foreground mt-1">Review all your past mock interviews and feedback.</p>
                </motion.div>

                {/* Filters */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="flex flex-col sm:flex-row gap-4 mb-6"
                >
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                            placeholder="Search by role or company..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-10"
                        />
                    </div>
                    <Select value={scoreFilter} onValueChange={setScoreFilter}>
                        <SelectTrigger className="w-full sm:w-48">
                            <Filter className="w-4 h-4 mr-2" />
                            <SelectValue placeholder="Filter by score" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Scores</SelectItem>
                            <SelectItem value="excellent">Excellent (85+)</SelectItem>
                            <SelectItem value="good">Good (70-84)</SelectItem>
                            <SelectItem value="needswork">Needs Work (&lt;70)</SelectItem>
                        </SelectContent>
                    </Select>
                </motion.div>

                {/* Results Count */}
                <p className="text-sm text-muted-foreground mb-4">
                    Showing {filteredInterviews.length} of {allInterviews.length} interviews
                </p>

                {/* Interview List */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                    className="bg-card rounded-xl border border-border shadow-sm"
                >
                    <div className="divide-y divide-border">
                        {filteredInterviews.length > 0 ? (
                            filteredInterviews.map((interview, i) => (
                                <motion.div
                                    key={interview.id}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.05 * i }}
                                    className="px-5 py-4 flex items-center justify-between hover:bg-muted/30 transition-colors"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="w-10 h-10 rounded-lg bg-primary/5 flex items-center justify-center">
                                            <Play className="w-4 h-4 text-primary" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-foreground">{interview.role}</p>
                                            <p className="text-xs text-muted-foreground">{interview.company} · {interview.date}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <div className="text-right">
                                            <div className="flex items-center gap-1">
                                                <Star className={`w-3.5 h-3.5 ${interview.score >= 80 ? "text-warning fill-warning" : "text-muted-foreground"}`} />
                                                <span className={`text-sm font-semibold ${interview.score >= 80 ? "text-foreground" : "text-muted-foreground"}`}>
                                                    {interview.score}%
                                                </span>
                                            </div>
                                            <p className="text-xs text-muted-foreground">{interview.duration}</p>
                                        </div>
                                        <Button variant="ghost" size="sm" asChild>
                                            <Link to="/feedback">
                                                <ArrowRight className="w-4 h-4" />
                                            </Link>
                                        </Button>
                                    </div>
                                </motion.div>
                            ))
                        ) : (
                            <div className="px-5 py-12 text-center">
                                <p className="text-muted-foreground">No interviews match your filters.</p>
                                <Button variant="ghost" size="sm" className="mt-2" onClick={() => { setSearchQuery(""); setScoreFilter("all"); }}>
                                    Clear Filters
                                </Button>
                            </div>
                        )}
                    </div>
                </motion.div>

                {/* Start New Interview CTA */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="mt-8 text-center"
                >
                    <Button variant="hero" size="lg" asChild>
                        <Link to="/interview">
                            Start New Mock Interview
                            <ArrowRight className="w-4 h-4 ml-1" />
                        </Link>
                    </Button>
                </motion.div>
            </main>
        </div>
    );
};

export default InterviewHistory;
