import { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { updateProfile, updateEmail, EmailAuthProvider, reauthenticateWithCredential } from "firebase/auth";
import { auth } from "@/lib/firebase";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { User, Save, LogOut, AlertCircle, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const Settings = () => {
    const { user, refreshUser, logout } = useAuth();
    const navigate = useNavigate();

    // Split Firebase displayName into first / last
    const splitName = (displayName = "") => {
        const parts = displayName.trim().split(" ");
        return {
            first: parts[0] || "",
            last:  parts.length > 1 ? parts.slice(1).join(" ") : "",
        };
    };

    const { first: initFirst, last: initLast } = splitName(user?.displayName || "");

    const [firstName,    setFirstName]    = useState(initFirst);
    const [lastName,     setLastName]     = useState(initLast);
    const [email,        setEmail]        = useState(user?.email || "");
    const [password,     setPassword]     = useState(""); // only needed to re-auth if email changes
    const [isSaving,     setIsSaving]     = useState(false);
    const [successMsg,   setSuccessMsg]   = useState("");
    const [errorMsg,     setErrorMsg]     = useState("");

    // Live initials from current form state
    const initials = firstName && lastName
        ? (firstName[0] + lastName[0]).toUpperCase()
        : firstName
        ? firstName[0].toUpperCase()
        : "U";

    const emailChanged = email.trim() !== (user?.email || "");

    const handleSave = async (e) => {
        e.preventDefault();
        setSuccessMsg("");
        setErrorMsg("");

        const newDisplayName = `${firstName.trim()} ${lastName.trim()}`.trim();
        if (!newDisplayName) {
            setErrorMsg("First name is required.");
            return;
        }
        if (!email.trim()) {
            setErrorMsg("Email is required.");
            return;
        }
        if (emailChanged && !password) {
            setErrorMsg("Enter your current password to change email.");
            return;
        }

        setIsSaving(true);
        try {
            const cu = auth.currentUser;
            if (!cu) throw new Error("Not signed in.");

            // Update display name
            await updateProfile(cu, { displayName: newDisplayName });

            // Changing email requires re-authentication
            if (emailChanged) {
                const credential = EmailAuthProvider.credential(cu.email, password);
                await reauthenticateWithCredential(cu, credential);
                await updateEmail(cu, email.trim());
            }

            await refreshUser();
            setPassword("");
            setSuccessMsg("Profile saved successfully.");
        } catch (err) {
            const map = {
                "auth/wrong-password":     "Incorrect current password.",
                "auth/email-already-in-use": "That email is already taken.",
                "auth/invalid-email":      "Invalid email address.",
                "auth/requires-recent-login": "Please sign out and sign back in, then try again.",
            };
            setErrorMsg(map[err.code] ?? err.message);
        } finally {
            setIsSaving(false);
        }
    };

    const handleLogout = async () => {
        await logout();
        navigate("/");
    };

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-2xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <h1 className="text-2xl font-bold text-foreground">Settings</h1>
                    <p className="text-muted-foreground mt-1">Manage your profile information.</p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 }}
                    className="bg-card rounded-xl border border-border shadow-sm"
                >
                    {/* Header */}
                    <div className="p-5 border-b border-border flex items-center gap-2">
                        <User className="w-4 h-4 text-cobalt" />
                        <h2 className="font-semibold text-foreground">Profile Information</h2>
                    </div>

                    <form onSubmit={handleSave} className="p-5 space-y-6">
                        {/* Avatar preview */}
                        <div className="flex items-center gap-4">
                            {user?.photoURL ? (
                                <img
                                    src={user.photoURL}
                                    alt={user.displayName}
                                    className="w-16 h-16 rounded-full object-cover border-2 border-cobalt/20"
                                />
                            ) : (
                                <div className="w-16 h-16 rounded-full gradient-cobalt flex items-center justify-center text-xl font-bold text-primary-foreground select-none">
                                    {initials}
                                </div>
                            )}
                            <div>
                                <p className="text-sm font-medium text-foreground">
                                    {`${firstName} ${lastName}`.trim() || "Your Name"}
                                </p>
                                <p className="text-xs text-muted-foreground mt-0.5">{user?.email}</p>
                                {user?.photoURL && (
                                    <p className="text-xs text-muted-foreground mt-1">
                                        Profile photo from Google account
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* Name fields */}
                        <div className="grid sm:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="firstName">First Name <span className="text-destructive">*</span></Label>
                                <Input
                                    id="firstName"
                                    value={firstName}
                                    onChange={(e) => { setFirstName(e.target.value); setSuccessMsg(""); }}
                                    placeholder="Jane"
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="lastName">Last Name</Label>
                                <Input
                                    id="lastName"
                                    value={lastName}
                                    onChange={(e) => { setLastName(e.target.value); setSuccessMsg(""); }}
                                    placeholder="Smith"
                                />
                            </div>
                        </div>

                        {/* Email */}
                        <div className="space-y-2">
                            <Label htmlFor="email">Email <span className="text-destructive">*</span></Label>
                            <Input
                                id="email"
                                type="email"
                                value={email}
                                onChange={(e) => { setEmail(e.target.value); setSuccessMsg(""); }}
                                placeholder="you@company.com"
                                required
                                disabled={!!user?.providerData?.find((p) => p.providerId === "google.com")}
                            />
                            {user?.providerData?.find((p) => p.providerId === "google.com") && (
                                <p className="text-xs text-muted-foreground">
                                    Email is managed by Google and cannot be changed here.
                                </p>
                            )}
                        </div>

                        {/* Current password — only shown when email is being changed */}
                        {emailChanged && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                className="space-y-2"
                            >
                                <Label htmlFor="password">
                                    Current Password{" "}
                                    <span className="text-xs text-muted-foreground font-normal">(required to change email)</span>
                                </Label>
                                <Input
                                    id="password"
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    autoComplete="current-password"
                                />
                            </motion.div>
                        )}

                        {/* Feedback */}
                        {errorMsg && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2"
                            >
                                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                                {errorMsg}
                            </motion.div>
                        )}

                        {successMsg && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex items-center gap-2 text-sm text-mint bg-mint/10 rounded-lg px-3 py-2"
                            >
                                <CheckCircle2 className="w-4 h-4 shrink-0" />
                                {successMsg}
                            </motion.div>
                        )}

                        {/* Actions */}
                        <div className="flex items-center gap-3 pt-2 border-t border-border">
                            <Button variant="hero" type="submit" disabled={isSaving} className="gap-2">
                                {isSaving ? (
                                    <>
                                        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                        Saving…
                                    </>
                                ) : (
                                    <>
                                        <Save className="w-4 h-4" />
                                        Save Changes
                                    </>
                                )}
                            </Button>

                            <Button
                                variant="ghost"
                                type="button"
                                onClick={handleLogout}
                                className="gap-1.5 text-muted-foreground hover:text-foreground ml-auto"
                            >
                                <LogOut className="w-4 h-4" />
                                Sign Out
                            </Button>
                        </div>
                    </form>
                </motion.div>
            </main>
        </div>
    );
};

export default Settings;
