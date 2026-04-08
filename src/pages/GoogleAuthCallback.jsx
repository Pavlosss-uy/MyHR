import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";

const GoogleAuthCallback = () => {
    const navigate = useNavigate();
    const { toast } = useToast();
    const { login } = useAuth();

    useEffect(() => {
        // Google returns tokens in the URL hash fragment for implicit flow
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);

        const accessToken = params.get("access_token");
        const state = params.get("state");
        const error = params.get("error");

        // Verify CSRF state
        const savedState = sessionStorage.getItem("google_oauth_state");
        sessionStorage.removeItem("google_oauth_state");

        if (error) {
            toast({
                title: "Authentication failed",
                description: `Google returned an error: ${error}`,
                variant: "destructive",
            });
            navigate("/auth");
            return;
        }

        if (!accessToken) {
            toast({
                title: "Authentication failed",
                description: "No access token received from Google.",
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

        // Token received — fetch user info from Google
        fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
            headers: { Authorization: `Bearer ${accessToken}` },
        })
            .then((res) => res.json())
            .then((userInfo) => {
                // Store user in auth context
                login({
                    name: userInfo.name || userInfo.email,
                    email: userInfo.email,
                    picture: userInfo.picture || null,
                    provider: "google",
                });

                toast({
                    title: "Welcome!",
                    description: `Signed in as ${userInfo.name || userInfo.email}`,
                });
                navigate("/candidate");
            })
            .catch(() => {
                toast({
                    title: "Authentication failed",
                    description: "Could not fetch user information from Google.",
                    variant: "destructive",
                });
                navigate("/auth");
            });
    }, [navigate, toast, login]);

    return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="text-center space-y-4">
                <div className="w-8 h-8 border-4 border-cobalt border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-muted-foreground">Completing Google sign-in...</p>
            </div>
        </div>
    );
};

export default GoogleAuthCallback;
