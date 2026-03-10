import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";

const LinkedInAuthCallback = () => {
    const navigate = useNavigate();
    const { toast } = useToast();
    const [searchParams] = useSearchParams();
    const { login } = useAuth();

    useEffect(() => {
        const code = searchParams.get("code");
        const state = searchParams.get("state");
        const error = searchParams.get("error");
        const errorDescription = searchParams.get("error_description");

        // Verify CSRF state
        const savedState = sessionStorage.getItem("linkedin_oauth_state");
        sessionStorage.removeItem("linkedin_oauth_state");

        if (error) {
            toast({
                title: "Authentication failed",
                description: errorDescription || `LinkedIn returned an error: ${error}`,
                variant: "destructive",
            });
            navigate("/auth");
            return;
        }

        if (!code) {
            toast({
                title: "Authentication failed",
                description: "No authorization code received from LinkedIn.",
                variant: "destructive",
            });
            navigate("/auth");
            return;
        }

        if (state !== savedState) {
            toast({
                title: "Authentication failed",
                description: "Invalid state parameter. Possible CSRF attack.",
                variant: "destructive",
            });
            navigate("/auth");
            return;
        }

        // LinkedIn uses authorization code flow — the code needs to be exchanged
        // for an access token on your backend server. For now, we store a placeholder
        // user. Replace this with your backend token exchange call to get real user info.
        //
        // Example backend call:
        // fetch("/api/auth/linkedin/callback", {
        //     method: "POST",
        //     headers: { "Content-Type": "application/json" },
        //     body: JSON.stringify({ code, redirectUri: `${window.location.origin}/auth/callback/linkedin` }),
        // })
        //     .then(res => res.json())
        //     .then(data => { login({ name: data.name, email: data.email, provider: "linkedin" }) })

        login({
            name: "LinkedIn User",
            email: "",
            provider: "linkedin",
        });

        toast({
            title: "LinkedIn sign-in successful!",
            description: "You have been authenticated with LinkedIn.",
        });
        navigate("/candidate");
    }, [navigate, toast, searchParams, login]);

    return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="text-center space-y-4">
                <div className="w-8 h-8 border-4 border-cobalt border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-muted-foreground">Completing LinkedIn sign-in...</p>
            </div>
        </div>
    );
};

export default LinkedInAuthCallback;
