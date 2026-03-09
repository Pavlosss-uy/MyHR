import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Welcome from "./pages/Welcome";
import Landing from "./pages/Landing";
import Auth from "./pages/Auth";
import GoogleAuthCallback from "./pages/GoogleAuthCallback";
import LinkedInAuthCallback from "./pages/LinkedInAuthCallback";
import HRDashboard from "./pages/HRDashboard";
import JobManagement from "./pages/JobManagement";
import Analytics from "./pages/Analytics";
import CandidateProfile from "./pages/CandidateProfile";
import CandidateHome from "./pages/CandidateHome";
import InterviewHistory from "./pages/InterviewHistory";
import InterviewRoom from "./pages/InterviewRoom";
import FeedbackReport from "./pages/FeedbackReport";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
    <QueryClientProvider client={queryClient}>
        <AuthProvider>
            <TooltipProvider>
                <Toaster />
                <Sonner />
                <BrowserRouter>
                    <Routes>
                        {/* Public routes */}
                        <Route path="/" element={<Welcome />} />
                        <Route path="/auth" element={<Auth />} />
                        <Route path="/auth/callback/google" element={<GoogleAuthCallback />} />
                        <Route path="/auth/callback/linkedin" element={<LinkedInAuthCallback />} />

                        {/* Protected routes — require login */}
                        <Route path="/home" element={<ProtectedRoute><Landing /></ProtectedRoute>} />
                        <Route path="/hr/dashboard" element={<ProtectedRoute><HRDashboard /></ProtectedRoute>} />
                        <Route path="/hr/jobs" element={<ProtectedRoute><JobManagement /></ProtectedRoute>} />
                        <Route path="/hr/analytics" element={<ProtectedRoute><Analytics /></ProtectedRoute>} />
                        <Route path="/hr/candidate/:id" element={<ProtectedRoute><CandidateProfile /></ProtectedRoute>} />
                        <Route path="/candidate" element={<ProtectedRoute><CandidateHome /></ProtectedRoute>} />
                        <Route path="/candidate/history" element={<ProtectedRoute><InterviewHistory /></ProtectedRoute>} />
                        <Route path="/interview" element={<ProtectedRoute><InterviewRoom /></ProtectedRoute>} />
                        <Route path="/feedback" element={<ProtectedRoute><FeedbackReport /></ProtectedRoute>} />
                        <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                        <Route path="*" element={<NotFound />} />
                    </Routes>
                </BrowserRouter>
            </TooltipProvider>
        </AuthProvider>
    </QueryClientProvider>
);

export default App;
