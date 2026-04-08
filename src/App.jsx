import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

// Public pages
import ChoiceScreen from "./pages/ChoiceScreen";
import Auth from "./pages/Auth";
import VerifyEmail from "./pages/VerifyEmail";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";

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
                        <Route path="/"             element={<ChoiceScreen />} />
                        <Route path="/landing"      element={<Landing />} />
                        <Route path="/auth"         element={<Auth />} />
                        <Route path="/verify-email" element={<VerifyEmail />} />

                        {/* OAuth callbacks (public — must complete before auth state settles) */}
                        <Route path="/auth/callback/google"   element={<GoogleAuthCallback />} />
                        <Route path="/auth/callback/linkedin" element={<LinkedInAuthCallback />} />

                        {/* ── Protected: Candidate ───────────────────────── */}
                        <Route
                            path="/candidate"
                            element={<ProtectedRoute><CandidateHome /></ProtectedRoute>}
                        />
                        <Route
                            path="/candidate/history"
                            element={<ProtectedRoute><InterviewHistory /></ProtectedRoute>}
                        />
                        <Route
                            path="/interview"
                            element={<ProtectedRoute><InterviewRoom /></ProtectedRoute>}
                        />
                        <Route
                            path="/feedback"
                            element={<ProtectedRoute><FeedbackReport /></ProtectedRoute>}
                        />

                        {/* ── Protected: HR ──────────────────────────────── */}
                        <Route
                            path="/hr/dashboard"
                            element={<ProtectedRoute><HRDashboard /></ProtectedRoute>}
                        />
                        <Route
                            path="/hr/jobs"
                            element={<ProtectedRoute><JobManagement /></ProtectedRoute>}
                        />
                        <Route
                            path="/hr/analytics"
                            element={<ProtectedRoute><Analytics /></ProtectedRoute>}
                        />
                        <Route
                            path="/hr/candidate/:id"
                            element={<ProtectedRoute><CandidateProfile /></ProtectedRoute>}
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
