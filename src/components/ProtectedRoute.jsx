import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2 } from "lucide-react";

const Spinner = () => (
    <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
    </div>
);

/**
 * Wraps any route that requires:
 *   1. A signed-in Firebase user
 *   2. A verified email address
 *   3. (optional) A specific role — requireRole="hr" | "candidate"
 *
 * Role is initialized synchronously from sessionStorage so returning users
 * never see a flicker-redirect. For fresh sessions with no cached role the
 * spinner is shown until the backend confirms the role.
 */
const ADMIN_EMAIL = "myhr2026@gmail.com";

const ProtectedRoute = ({ children, requireRole }) => {
    const { user, loading, isAuthenticated, emailVerified, userRole, roleLoading } = useAuth();
    const location = useLocation();

    if (loading) return <Spinner />;

    if (!isAuthenticated) {
        return <Navigate to="/auth" state={{ from: location }} replace />;
    }

    if (!emailVerified) {
        return <Navigate to="/verify-email" replace />;
    }

    // Admin email always bypasses role restrictions
    const isAdmin = user?.email === ADMIN_EMAIL;
    if (isAdmin) return children;

    // Wait for role to be determined before enforcing access control.
    // This prevents the "flash then redirect" for fresh sessions.
    if (requireRole && roleLoading) return <Spinner />;

    // Role confirmed and mismatched — send user to their correct home immediately.
    if (requireRole && userRole && userRole !== requireRole) {
        const home = userRole === "hr" ? "/hr/dashboard" : "/candidate";
        return <Navigate to={home} replace />;
    }

    return children;
};

export default ProtectedRoute;
