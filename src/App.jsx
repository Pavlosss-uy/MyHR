import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Auth from "./pages/Auth";
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
        <TooltipProvider>
            <Toaster />
            <Sonner />
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Landing />} />
                    <Route path="/auth" element={<Auth />} />
                    <Route path="/hr/dashboard" element={<HRDashboard />} />
                    <Route path="/hr/jobs" element={<JobManagement />} />
                    <Route path="/hr/analytics" element={<Analytics />} />
                    <Route path="/hr/candidate/:id" element={<CandidateProfile />} />
                    <Route path="/candidate" element={<CandidateHome />} />
                    <Route path="/candidate/history" element={<InterviewHistory />} />
                    <Route path="/interview" element={<InterviewRoom />} />
                    <Route path="/feedback" element={<FeedbackReport />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="*" element={<NotFound />} />
                </Routes>
            </BrowserRouter>
        </TooltipProvider>
    </QueryClientProvider>
);

export default App;
