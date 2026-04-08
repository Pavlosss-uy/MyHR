import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2 } from "lucide-react";

/**
 * Wraps any route that requires:
 *   1. A signed-in Firebase user
 *   2. A verified email address
 *
 * While Firebase resolves the auth state (loading === true) a full-screen
 * spinner is shown instead of a flash-redirect.
 */
const ProtectedRoute = ({ children }) => {
    const { user, loading, isAuthenticated, emailVerified } = useAuth();
    const location = useLocation();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="w-8 h-8 animate-spin text-cobalt" />
            </div>
        );
    }

    if (!isAuthenticated) {
        // Remember where the user was trying to go
        return <Navigate to="/auth" state={{ from: location }} replace />;
    }

    if (!emailVerified) {
        return <Navigate to="/verify-email" replace />;
    }

    return children;
};

export default ProtectedRoute;
