import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import Navbar from "@/components/Navbar";
import StatCard from "@/components/StatCard";
import { Button } from "@/components/ui/button";
import {
    BarChart3,
    TrendingUp,
    Users,
    Clock,
    ArrowLeft,
    Calendar,
    Target,
    Award
} from "lucide-react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    BarChart,
    Bar,
} from "recharts";

const interviewTrends = [
    { month: "Sep", interviews: 45, hired: 12 },
    { month: "Oct", interviews: 62, hired: 18 },
    { month: "Nov", interviews: 58, hired: 15 },
    { month: "Dec", interviews: 71, hired: 22 },
    { month: "Jan", interviews: 85, hired: 28 },
    { month: "Feb", interviews: 92, hired: 31 },
];

const departmentData = [
    { dept: "Engineering", candidates: 89, avgScore: 82 },
    { dept: "Product", candidates: 45, avgScore: 78 },
    { dept: "Design", candidates: 32, avgScore: 85 },
    { dept: "Marketing", candidates: 28, avgScore: 76 },
    { dept: "Sales", candidates: 53, avgScore: 74 },
];

const Analytics = () => {
    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-7xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
                        <Link to="/hr/dashboard">
                            <ArrowLeft className="w-4 h-4 mr-1" />
                            Back to Dashboard
                        </Link>
                    </Button>
                    <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
                    <p className="text-muted-foreground mt-1">Track your hiring metrics and trends.</p>
                </motion.div>

                {/* Stats Row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <StatCard icon={Users} label="Total Interviews" value="413" change="+23%" changeType="positive" />
                    <StatCard icon={Target} label="Hire Rate" value="34%" change="+5%" changeType="positive" />
                    <StatCard icon={Clock} label="Avg. Time to Hire" value="18 days" change="-3 days" changeType="positive" />
                    <StatCard icon={Award} label="Avg. Score" value="79%" change="+2%" changeType="positive" />
                </div>

                <div className="grid lg:grid-cols-2 gap-6 mb-8">
                    {/* Interview Trends */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="bg-card rounded-xl border border-border shadow-sm p-6"
                    >
                        <div className="flex items-center gap-2 mb-6">
                            <TrendingUp className="w-5 h-5 text-cobalt" />
                            <h3 className="font-semibold text-foreground">Interview Trends</h3>
                        </div>
                        <div className="h-64">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={interviewTrends}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                                    <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                                    <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: "hsl(var(--card))",
                                            border: "1px solid hsl(var(--border))",
                                            borderRadius: "8px"
                                        }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="interviews"
                                        stroke="hsl(222 64% 45%)"
                                        strokeWidth={2}
                                        dot={{ fill: "hsl(222 64% 45%)" }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="hired"
                                        stroke="hsl(160 60% 45%)"
                                        strokeWidth={2}
                                        dot={{ fill: "hsl(160 60% 45%)" }}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="flex items-center justify-center gap-6 mt-4">
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full bg-cobalt" />
                                <span className="text-sm text-muted-foreground">Interviews</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full bg-mint" />
                                <span className="text-sm text-muted-foreground">Hired</span>
                            </div>
                        </div>
                    </motion.div>

                    {/* Department Performance */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="bg-card rounded-xl border border-border shadow-sm p-6"
                    >
                        <div className="flex items-center gap-2 mb-6">
                            <BarChart3 className="w-5 h-5 text-mint" />
                            <h3 className="font-semibold text-foreground">By Department</h3>
                        </div>
                        <div className="h-64">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={departmentData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                                    <XAxis dataKey="dept" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                                    <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: "hsl(var(--card))",
                                            border: "1px solid hsl(var(--border))",
                                            borderRadius: "8px"
                                        }}
                                    />
                                    <Bar dataKey="candidates" fill="hsl(222 64% 45%)" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </motion.div>
                </div>

                {/* Recent Activity */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="bg-card rounded-xl border border-border shadow-sm"
                >
                    <div className="p-5 border-b border-border flex items-center gap-2">
                        <Calendar className="w-5 h-5 text-cobalt" />
                        <h3 className="font-semibold text-foreground">Recent Activity</h3>
                    </div>
                    <div className="divide-y divide-border">
                        {[
                            { action: "Interview completed", candidate: "Sarah Chen", role: "Senior Engineer", time: "2 hours ago" },
                            { action: "Candidate hired", candidate: "Marcus Johnson", role: "Product Manager", time: "5 hours ago" },
                            { action: "New application", candidate: "Emily Park", role: "UX Designer", time: "1 day ago" },
                            { action: "Feedback sent", candidate: "David Kim", role: "Backend Dev", time: "1 day ago" },
                        ].map((item, i) => (
                            <div key={i} className="px-5 py-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                                <div>
                                    <p className="text-sm font-medium text-foreground">{item.action}</p>
                                    <p className="text-xs text-muted-foreground">{item.candidate} — {item.role}</p>
                                </div>
                                <span className="text-xs text-muted-foreground">{item.time}</span>
                            </div>
                        ))}
                    </div>
                </motion.div>
            </main>
        </div>
    );
};

export default Analytics;
