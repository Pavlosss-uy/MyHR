import { createContext, useContext, useState, useEffect } from "react";
import {
    onAuthStateChanged,
    signOut,
    updateProfile,
    updateEmail,
    reload,
} from "firebase/auth";
import { auth } from "@/lib/firebase";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    // null  → still loading
    // false → loaded, not signed in
    // object → Firebase user
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
            setUser(firebaseUser);
            setLoading(false);
        });
        return unsubscribe;
    }, []);

    // Derived convenience flags
    const isAuthenticated = !!user;
    const emailVerified = user?.emailVerified ?? false;

    // Update display name + photoURL in Firebase
    const updateUserProfile = async ({ displayName, photoURL }) => {
        if (!auth.currentUser) return;
        await updateProfile(auth.currentUser, { displayName, photoURL });
        // Force a state refresh so consuming components re-render
        setUser({ ...auth.currentUser });
    };

    // Update email in Firebase
    const updateUserEmail = async (newEmail) => {
        if (!auth.currentUser) return;
        await updateEmail(auth.currentUser, newEmail);
        setUser({ ...auth.currentUser });
    };

    // Reload the Firebase user (e.g. after email verification)
    const refreshUser = async () => {
        if (!auth.currentUser) return;
        await reload(auth.currentUser);
        setUser({ ...auth.currentUser });
    };

    const logout = async () => {
        sessionStorage.removeItem("myhr_role");
        await signOut(auth);
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                loading,
                isAuthenticated,
                emailVerified,
                updateUserProfile,
                updateUserEmail,
                refreshUser,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
};
