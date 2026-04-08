import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Brain, Menu, X, LogOut, Settings } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

const Navbar = () => {
    const [mobileOpen, setMobileOpen] = useState(false);
    const location  = useLocation();
    const navigate  = useNavigate();
    const { user, isAuthenticated, logout } = useAuth();

    const handleLogout = async () => {
        await logout();
        navigate("/");
    };

    const getInitials = (name) => {
        if (!name) return "U";
        const parts = name.trim().split(" ");
        return parts.length >= 2
            ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
            : name[0].toUpperCase();
    };

    // Firebase user fields
    const displayName = user?.displayName || user?.email?.split("@")[0] || "User";
    const firstName   = displayName.split(" ")[0];
    const photoURL    = user?.photoURL ?? null;
    const initials    = getInitials(displayName);

    const AvatarBadge = ({ className = "" }) => (
        photoURL ? (
            <img
                src={photoURL}
                alt={displayName}
                className={cn("rounded-full object-cover border-2 border-cobalt/20", className)}
            />
        ) : (
            <div className={cn("rounded-full gradient-cobalt flex items-center justify-center font-bold text-primary-foreground", className)}>
                {initials}
            </div>
        )
    );

    return (
        <nav className="fixed top-0 left-0 right-0 z-50 glass">
            <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">

                {/* Brand — always goes to "/" */}
                <Link to="/" className="flex items-center gap-2.5 group">
                    <div className="w-9 h-9 rounded-lg gradient-cobalt flex items-center justify-center shadow-cobalt">
                        <Brain className="w-5 h-5 text-primary-foreground" />
                    </div>
                    <span className="text-lg font-bold text-foreground tracking-tight">
                        Interv<span className="text-cobalt-light">AI</span>
                    </span>
                </Link>

                {/* Desktop right section */}
                <div className="hidden md:flex items-center gap-3">
                    {isAuthenticated ? (
                        <>
                            <Link
                                to="/settings"
                                className={cn(
                                    "p-2 rounded-lg transition-colors",
                                    location.pathname === "/settings"
                                        ? "text-primary bg-primary/5"
                                        : "text-muted-foreground hover:text-foreground hover:bg-muted"
                                )}
                                title="Settings"
                            >
                                <Settings className="w-4 h-4" />
                            </Link>

                            <div className="flex items-center gap-2.5">
                                <AvatarBadge className="w-8 h-8 text-xs" />
                                <span className="text-sm font-medium text-foreground">{firstName}</span>
                            </div>

                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleLogout}
                                className="gap-1.5 text-muted-foreground hover:text-foreground"
                            >
                                <LogOut className="w-4 h-4" />
                                Sign Out
                            </Button>
                        </>
                    ) : (
                        <Button variant="ghost" size="sm" asChild>
                            <Link to="/auth">Sign In</Link>
                        </Button>
                    )}
                </div>

                {/* Mobile hamburger */}
                <button
                    className="md:hidden p-2 text-foreground"
                    onClick={() => setMobileOpen((o) => !o)}
                    aria-label="Toggle menu"
                >
                    {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </button>
            </div>

            {/* Mobile menu */}
            {mobileOpen && (
                <div className="md:hidden glass-strong border-t border-border px-6 py-4 space-y-2">
                    {isAuthenticated ? (
                        <>
                            <div className="flex items-center gap-2.5 px-4 py-2">
                                <AvatarBadge className="w-8 h-8 text-xs" />
                                <span className="text-sm font-medium text-foreground">{firstName}</span>
                            </div>

                            <Link
                                to="/settings"
                                onClick={() => setMobileOpen(false)}
                                className="flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-foreground rounded-lg hover:bg-muted"
                            >
                                <Settings className="w-4 h-4" />
                                Settings
                            </Link>

                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => { handleLogout(); setMobileOpen(false); }}
                                className="gap-1.5 w-full justify-start px-4"
                            >
                                <LogOut className="w-4 h-4" />
                                Sign Out
                            </Button>
                        </>
                    ) : (
                        <Button variant="ghost" size="sm" asChild className="w-full">
                            <Link to="/auth" onClick={() => setMobileOpen(false)}>Sign In</Link>
                        </Button>
                    )}
                </div>
            )}
        </nav>
    );
};

export default Navbar;
