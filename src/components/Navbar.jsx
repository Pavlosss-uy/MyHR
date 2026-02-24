import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Brain, Menu, X } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const navLinks = [
    { label: "For HR", href: "/hr/dashboard" },
    { label: "For Candidates", href: "/candidate" },
    { label: "Features", href: "/#features" },
    { label: "Settings", href: "/settings" },
];

const Navbar = () => {
    const [mobileOpen, setMobileOpen] = useState(false);
    const location = useLocation();

    return (
        <nav className="fixed top-0 left-0 right-0 z-50 glass">
            <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                <Link to="/" className="flex items-center gap-2.5 group">
                    <div className="w-9 h-9 rounded-lg gradient-cobalt flex items-center justify-center shadow-cobalt">
                        <Brain className="w-5 h-5 text-primary-foreground" />
                    </div>
                    <span className="text-lg font-bold text-foreground tracking-tight">
                        My<span className="text-cobalt-light">HR</span>
                    </span>
                </Link>

                <div className="hidden md:flex items-center gap-1">
                    {navLinks.map((link) => (
                        <Link
                            key={link.href}
                            to={link.href}
                            className={cn(
                                "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
                                location.pathname === link.href
                                    ? "text-primary bg-primary/5"
                                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                            )}
                        >
                            {link.label}
                        </Link>
                    ))}
                </div>

                <div className="hidden md:flex items-center gap-3">
                    <Button variant="ghost" size="sm" asChild>
                        <Link to="/auth">Sign In</Link>
                    </Button>
                    <Button variant="hero" size="sm" asChild>
                        <Link to="/auth?mode=signup">Get Started</Link>
                    </Button>
                </div>

                <button
                    className="md:hidden p-2 text-foreground"
                    onClick={() => setMobileOpen(!mobileOpen)}
                >
                    {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </button>
            </div>

            {mobileOpen && (
                <div className="md:hidden glass-strong border-t border-border px-6 py-4 space-y-2">
                    {navLinks.map((link) => (
                        <Link
                            key={link.href}
                            to={link.href}
                            onClick={() => setMobileOpen(false)}
                            className="block px-4 py-2.5 text-sm font-medium text-foreground rounded-lg hover:bg-muted"
                        >
                            {link.label}
                        </Link>
                    ))}
                    <div className="pt-2 flex flex-col gap-2">
                        <Button variant="ghost" size="sm" asChild>
                            <Link to="/auth" onClick={() => setMobileOpen(false)}>Sign In</Link>
                        </Button>
                        <Button variant="hero" size="sm" asChild>
                            <Link to="/auth?mode=signup" onClick={() => setMobileOpen(false)}>Get Started</Link>
                        </Button>
                    </div>
                </div>
            )}
        </nav>
    );
};

export default Navbar;
