import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Loader2 } from "lucide-react";

// Public pages
import ChoiceScreen from "./pages/ChoiceScreen";
import Auth from "./pages/Auth";
import VerifyEmail from "./pages/VerifyEmail";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";

// B2B pages
import RequestAccess from "./pages/RequestAccess";
import AcceptInvitation from "./pages/AcceptInvitation";
import AdminPendingRequests from "./pages/AdminPendingRequests";
import CandidateInterviewPortal from "./pages/CandidateInterviewPortal";

/**
 * Wraps the landing page so authenticated users are redirected to their
 * dashboard immediately — they should never see the marketing page again
 * after signing in.
 */
const SmartLanding = () => {
    const { isAuthenticated, loading, isAdmin } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
            </div>
        );
    }

    if (isAuthenticated) {
        if (isAdmin) return <Navigate to="/admin/requests" replace />;
        const role = sessionStorage.getItem("myhr_role") || "candidate";
        return <Navigate to={role === "hr" ? "/hr/dashboard" : "/candidate"} replace />;
    }

    return <Landing />;
};

/**
 * Restricts a route to the myhr admin account only.
 * Any authenticated non-admin is sent back to the HR dashboard.
 */
const AdminRoute = ({ children }) => {
    const { isAuthenticated, loading, isAdmin } = useAuth();
    const location = useLocation();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/auth" state={{ from: location }} replace />;
    }

    if (!isAdmin) {
        return <Navigate to="/hr/dashboard" replace />;
    }

    return children;
};

// Auth callbacks
import GoogleAuthCallback from "./pages/GoogleAuthCallback";
import LinkedInAuthCallback from "./pages/LinkedInAuthCallback";

// Protected — candidate
import CandidateHome from "./pages/CandidateHome";
import InterviewHistory from "./pages/InterviewHistory";
import InterviewRoom from "./pages/InterviewRoom";
import FeedbackReport from "./pages/FeedbackReport";

// Protected — HR
import HRDashboard from "./pages/HRDashboard";
import JobManagement from "./pages/JobManagement";
import Analytics from "./pages/Analytics";
import CandidateProfile from "./pages/CandidateProfile";

// Shared protected
import Settings from "./pages/Settings";

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 1000 * 60 * 5, // 5 min
            retry: 1,
        },
    },
});

const App = () => (
    <QueryClientProvider client={queryClient}>
        <AuthProvider>
            <TooltipProvider>
                <Toaster />
                <Sonner richColors position="top-right" />
                <BrowserRouter>
                    <Routes>
                        {/* ── Public ─────────────────────────────────────── */}
                        <Route path="/"             element={<SmartLanding />} />
                        <Route path="/choose"       element={<ChoiceScreen />} />
                        <Route path="/landing"      element={<SmartLanding />} />
                        <Route path="/auth"         element={<Auth />} />
                        <Route path="/verify-email" element={<VerifyEmail />} />

                        {/* B2B public routes */}
                        <Route path="/request-access"             element={<RequestAccess />} />
                        <Route path="/invite/:token"              element={<AcceptInvitation />} />
                        <Route path="/candidate-interview/:token" element={<CandidateInterviewPortal />} />

                        {/* Admin-only — myhr account only */}
                        <Route
                            path="/admin/requests"
                            element={<AdminRoute><AdminPendingRequests /></AdminRoute>}
                        />

                        {/* OAuth callbacks (public — must complete before auth state settles) */}
                        <Route path="/auth/callback/google"   element={<GoogleAuthCallback />} />
                        <Route path="/auth/callback/linkedin" element={<LinkedInAuthCallback />} />

                        {/* ── Protected: Candidate ───────────────────────── */}
                        <Route
                            path="/candidate"
                            element={<ProtectedRoute requireRole="candidate"><CandidateHome /></ProtectedRoute>}
                        />
                        <Route
                            path="/candidate/history"
                            element={<ProtectedRoute requireRole="candidate"><InterviewHistory /></ProtectedRoute>}
                        />
                        <Route
                            path="/interview"
                            element={<ProtectedRoute requireRole="candidate"><InterviewRoom /></ProtectedRoute>}
                        />
                        <Route
                            path="/feedback"
                            element={<ProtectedRoute requireRole="candidate"><FeedbackReport /></ProtectedRoute>}
                        />

                        {/* ── Protected: HR ──────────────────────────────── */}
                        <Route
                            path="/hr/dashboard"
                            element={<ProtectedRoute requireRole="hr"><HRDashboard /></ProtectedRoute>}
                        />
                        <Route
                            path="/hr/jobs"
                            element={<ProtectedRoute requireRole="hr"><JobManagement /></ProtectedRoute>}
                        />
                        <Route
                            path="/hr/analytics"
                            element={<ProtectedRoute requireRole="hr"><Analytics /></ProtectedRoute>}
                        />
                        <Route
                            path="/hr/candidate/:id"
                            element={<ProtectedRoute requireRole="hr"><CandidateProfile /></ProtectedRoute>}
                        />

                        {/* ── Shared protected ───────────────────────────── */}
                        <Route
                            path="/settings"
                            element={<ProtectedRoute><Settings /></ProtectedRoute>}
                        />

                        {/* ── Fallback ───────────────────────────────────── */}
                        <Route path="*" element={<NotFound />} />
                    </Routes>
                </BrowserRouter>
            </TooltipProvider>
        </AuthProvider>
    </QueryClientProvider>
);

export default App;
