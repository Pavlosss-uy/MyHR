import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import Navbar from "@/components/Navbar";
import StatCard from "@/components/StatCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { getAnalytics } from "@/lib/interviewApi";
import {
    BarChart3,
    TrendingUp,
    Users,
    Clock,
    ArrowLeft,
    Calendar,
    Target,
    Award,
    Loader2,
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

const ChartTooltipStyle = {
    backgroundColor: "hsl(var(--card))",
    border: "1px solid hsl(var(--border))",
    borderRadius: "8px",
    fontSize: "12px",
};

const Analytics = () => {
    const { user, loading: authLoading } = useAuth();
    const [data, setData]     = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (authLoading) return;
        if (!user) { setLoading(false); return; }
        (async () => {
            try {
                const result = await getAnalytics();
                setData(result);
            } catch (err) {
                console.error("Analytics fetch error:", err);
            } finally {
                setLoading(false);
            }
        })();
    }, [user, authLoading]);

    const stats          = data?.stats          || {};
    const monthlyTrends  = data?.monthly_trends  || [];
    const jobsBreakdown  = data?.jobs_breakdown  || [];
    const recentActivity = data?.recent_activity || [];

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-7xl mx-auto px-6">
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
                    <Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
                        <Link to="/hr/dashboard">
                            <ArrowLeft className="w-4 h-4 mr-1" />
                            Back to Dashboard
                        </Link>
                    </Button>
                    <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
                    <p className="text-muted-foreground mt-1">Real hiring metrics for your account.</p>
                </motion.div>

                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
                    </div>
                ) : (
                    <>
                        {/* Stats Row */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                            <StatCard
                                icon={Users}
                                label="Total Candidates"
                                value={(stats.total_candidates ?? 0).toString()}
                                change={stats.total_candidates > 0 ? `${stats.total_candidates} total` : ""}
                                changeType="neutral"
                            />
                            <StatCard
                                icon={Target}
                                label="Interviewed"
                                value={(stats.total_interviewed ?? 0).toString()}
                                change={stats.total_interviewed > 0 ? "completed" : ""}
                                changeType="positive"
                            />
                            <StatCard
                                icon={Clock}
                                label="Avg. Match Score"
                                value={`${stats.avg_match_score ?? 0}%`}
                                change={stats.avg_match_score > 70 ? "above threshold" : ""}
                                changeType={stats.avg_match_score > 70 ? "positive" : "neutral"}
                            />
                            <StatCard
                                icon={Award}
                                label="Avg. Interview Score"
                                value={stats.total_interviewed > 0 ? `${stats.avg_interview_score ?? 0}%` : "—"}
                                change={stats.avg_interview_score >= 70 ? "above threshold" : ""}
                                changeType={stats.avg_interview_score >= 70 ? "positive" : "neutral"}
                            />
                        </div>

                        <div className="grid lg:grid-cols-2 gap-6 mb-8">
                            {/* Monthly Trends */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.1 }}
                                className="bg-card rounded-xl border border-border shadow-sm p-6"
                            >
                                <div className="flex items-center gap-2 mb-6">
                                    <TrendingUp className="w-5 h-5 text-cobalt" />
                                    <h3 className="font-semibold text-foreground">Monthly Trends</h3>
                                </div>
                                {monthlyTrends.length > 0 ? (
                                    <>
                                        <div className="h-64">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={monthlyTrends}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                                                    <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                                                    <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} allowDecimals={false} />
                                                    <Tooltip contentStyle={ChartTooltipStyle} />
                                                    <Line
                                                        type="monotone"
                                                        dataKey="candidates"
                                                        name="Candidates"
                                                        stroke="hsl(222 64% 45%)"
                                                        strokeWidth={2}
                                                        dot={{ fill: "hsl(222 64% 45%)" }}
                                                    />
                                                    <Line
                                                        type="monotone"
                                                        dataKey="interviewed"
                                                        name="Interviewed"
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
                                                <span className="text-sm text-muted-foreground">Candidates</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <div className="w-3 h-3 rounded-full bg-mint" />
                                                <span className="text-sm text-muted-foreground">Interviewed</span>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div className="h-64 flex flex-col items-center justify-center gap-2 text-muted-foreground">
                                        <BarChart3 className="w-8 h-8 opacity-30" />
                                        <p className="text-sm">No trend data yet. Upload CVs to see trends.</p>
                                    </div>
                                )}
                            </motion.div>

                            {/* Jobs Breakdown */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.2 }}
                                className="bg-card rounded-xl border border-border shadow-sm p-6"
                            >
                                <div className="flex items-center gap-2 mb-6">
                                    <BarChart3 className="w-5 h-5 text-mint" />
                                    <h3 className="font-semibold text-foreground">By Job Position</h3>
                                </div>
                                {jobsBreakdown.filter(j => j.candidates > 0).length > 0 ? (
                                    <div className="h-64">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={jobsBreakdown.filter(j => j.candidates > 0)} margin={{ bottom: 24 }}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                                                <XAxis
                                                    dataKey="title"
                                                    stroke="hsl(var(--muted-foreground))"
                                                    fontSize={11}
                                                    angle={-20}
                                                    textAnchor="end"
                                                    interval={0}
                                                    tick={{ width: 80 }}
                                                />
                                                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} allowDecimals={false} />
                                                <Tooltip contentStyle={ChartTooltipStyle} />
                                                <Bar
                                                    dataKey="candidates"
                                                    name="Candidates"
                                                    fill="hsl(222 64% 45%)"
                                                    radius={[4, 4, 0, 0]}
                                                />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                ) : (
                                    <div className="h-64 flex flex-col items-center justify-center gap-2 text-muted-foreground">
                                        <Users className="w-8 h-8 opacity-30" />
                                        <p className="text-sm">No job data yet. Create a job and upload CVs.</p>
                                    </div>
                                )}
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
                            {recentActivity.length > 0 ? (
                                <div className="divide-y divide-border">
                                    {recentActivity.map((item, i) => (
                                        <div
                                            key={i}
                                            className="px-5 py-4 flex items-center justify-between hover:bg-muted/30 transition-colors"
                                        >
                                            <div>
                                                <p className="text-sm font-medium text-foreground">{item.action}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {item.candidate} — {item.job}
                                                </p>
                                            </div>
                                            <span className="text-xs text-muted-foreground shrink-0 ml-4">
                                                {item.time_ago || ""}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="p-8 text-center">
                                    <p className="text-sm text-muted-foreground">
                                        No completed interviews yet. Invite candidates to get started.
                                    </p>
                                </div>
                            )}
                        </motion.div>
                    </>
                )}
            </main>
        </div>
    );
};

export default Analytics;
