import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import StatCard from "@/components/StatCard";
import CircularProgress from "@/components/CircularProgress";
import { Users, Briefcase, Clock, TrendingUp, Star, MoreHorizontal, Play, BarChart3, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";

const leaderboard = [
    { rank: 1, id: "1", name: "Sarah Chen", role: "Senior Engineer", score: 94, status: "Recommended" },
    { rank: 2, id: "2", name: "Marcus Johnson", role: "Product Manager", score: 89, status: "Recommended" },
    { rank: 3, id: "3", name: "Priya Sharma", role: "Data Scientist", score: 86, status: "Under Review" },
    { rank: 4, id: "4", name: "Alex Rivera", role: "UX Designer", score: 82, status: "Under Review" },
    { rank: 5, id: "5", name: "Jordan Lee", role: "Frontend Dev", score: 78, status: "Needs Improvement" },
];

const recentInterviews = [
    { candidate: "Sarah Chen", role: "Senior Engineer", time: "2 hours ago", score: 94 },
    { candidate: "Marcus Johnson", role: "Product Manager", time: "5 hours ago", score: 89 },
    { candidate: "Priya Sharma", role: "Data Scientist", time: "1 day ago", score: 86 },
    { candidate: "David Kim", role: "Backend Dev", time: "1 day ago", score: 71 },
];

const statusColors = {
    Recommended: "bg-mint-light text-mint-dark",
    "Under Review": "bg-warning/10 text-warning",
    "Needs Improvement": "bg-destructive/10 text-destructive",
};

const HRDashboard = () => {
    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-7xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
                >
                    <div>
                        <h1 className="text-2xl font-bold text-foreground">HR Dashboard</h1>
                        <p className="text-muted-foreground mt-1">Overview of your hiring pipeline and candidate performance.</p>
                    </div>
                    <div className="flex gap-3">
                        <Button variant="outline" size="sm" asChild>
                            <Link to="/hr/analytics">
                                <BarChart3 className="w-4 h-4 mr-1.5" />
                                Analytics
                            </Link>
                        </Button>
                        <Button variant="hero" size="sm" asChild>
                            <Link to="/hr/jobs">
                                <Plus className="w-4 h-4 mr-1.5" />
                                New Job
                            </Link>
                        </Button>
                    </div>
                </motion.div>

                {/* Stats Row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <StatCard icon={Users} label="Total Candidates" value="247" change="+12%" changeType="positive" />
                    <StatCard icon={Briefcase} label="Open Positions" value="18" change="+3" changeType="positive" />
                    <StatCard icon={Clock} label="Avg Interview Time" value="24m" change="-2m" changeType="positive" />
                    <StatCard icon={TrendingUp} label="Hire Rate" value="34%" change="+5%" changeType="positive" />
                </div>

                <div className="grid lg:grid-cols-3 gap-6">
                    {/* Leaderboard */}
                    <div className="lg:col-span-2 bg-card rounded-xl border border-border shadow-sm">
                        <div className="p-5 border-b border-border flex items-center justify-between">
                            <div>
                                <h2 className="font-semibold text-foreground">Candidate Leaderboard</h2>
                                <p className="text-sm text-muted-foreground mt-0.5">Top performers from recent interviews</p>
                            </div>
                            <Button variant="ghost" size="icon">
                                <MoreHorizontal className="w-4 h-4" />
                            </Button>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-border">
                                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">Rank</th>
                                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">Candidate</th>
                                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">Score</th>
                                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">Status</th>
                                        <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {leaderboard.map((candidate) => (
                                        <tr key={candidate.rank} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                                            <td className="px-5 py-3.5">
                                                <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${candidate.rank <= 3 ? "gradient-cobalt text-primary-foreground" : "bg-muted text-muted-foreground"
                                                    }`}>
                                                    {candidate.rank}
                                                </span>
                                            </td>
                                            <td className="px-5 py-3.5">
                                                <div>
                                                    <Link to={`/hr/candidate/${candidate.id}`} className="text-sm font-medium text-foreground hover:text-primary transition-colors">
                                                        {candidate.name}
                                                    </Link>
                                                    <p className="text-xs text-muted-foreground">{candidate.role}</p>
                                                </div>
                                            </td>
                                            <td className="px-5 py-3.5">
                                                <div className="flex items-center gap-1.5">
                                                    <Star className="w-3.5 h-3.5 text-warning fill-warning" />
                                                    <span className="text-sm font-semibold text-foreground">{candidate.score}</span>
                                                </div>
                                            </td>
                                            <td className="px-5 py-3.5">
                                                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${statusColors[candidate.status]}`}>
                                                    {candidate.status}
                                                </span>
                                            </td>
                                            <td className="px-5 py-3.5 text-right">
                                                <Button variant="ghost" size="sm" asChild>
                                                    <Link to="/feedback">View Report</Link>
                                                </Button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Right Column */}
                    <div className="space-y-6">
                        {/* Hiring Health */}
                        <div className="bg-card rounded-xl border border-border shadow-sm p-5">
                            <h3 className="font-semibold text-foreground mb-4">Hiring Health</h3>
                            <div className="grid grid-cols-2 gap-4">
                                <CircularProgress value={87} size={100} label="Pipeline" color="cobalt" />
                                <CircularProgress value={72} size={100} label="Quality" color="mint" />
                            </div>
                        </div>

                        {/* Latest Interviews */}
                        <div className="bg-card rounded-xl border border-border shadow-sm">
                            <div className="p-5 border-b border-border">
                                <h3 className="font-semibold text-foreground">Latest Interviews</h3>
                            </div>
                            <div className="divide-y divide-border">
                                {recentInterviews.map((interview, i) => (
                                    <Link key={i} to="/feedback" className="block px-5 py-3.5 flex items-center justify-between hover:bg-muted/30 transition-colors cursor-pointer">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full gradient-cobalt flex items-center justify-center">
                                                <Play className="w-3 h-3 text-primary-foreground" />
                                            </div>
                                            <div>
                                                <p className="text-sm font-medium text-foreground">{interview.candidate}</p>
                                                <p className="text-xs text-muted-foreground">{interview.time}</p>
                                            </div>
                                        </div>
                                        <span className="text-sm font-semibold text-foreground">{interview.score}%</span>
                                    </Link>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default HRDashboard;
