import { createContext, useContext, useState, useEffect } from "react";
import {
    onAuthStateChanged,
    signOut,
    updateProfile,
    updateEmail,
    reload,
} from "firebase/auth";
import { auth } from "@/lib/firebase";

// ── Super Admin constants (exported so Auth.jsx can reuse them) ──────────────
export const ADMIN_EMAIL    = "myhr2026@gmail.com";
export const ADMIN_PASSWORD = "123456";
const ROLE_KEY = "myhr_role";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    // Initialize synchronously from sessionStorage to avoid flash-redirects.
    // If nothing is cached, roleLoading=true until the backend confirms the role.
    const [userRole, setUserRole] = useState(() => sessionStorage.getItem(ROLE_KEY) || null);
    const [roleLoading, setRoleLoading] = useState(!sessionStorage.getItem(ROLE_KEY));

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
            setUser(firebaseUser);
            setLoading(false);

            if (!firebaseUser) {
                setUserRole(null);
                setRoleLoading(false);
                return;
            }

            // ── Super Admin fast-path ────────────────────────────────────
            // If the signed-in email is the admin email (email/password OR
            // Google OAuth), immediately grant the "hr" role and skip all
            // backend lookups. This guarantees zero flicker for admin.
            if (firebaseUser.email === ADMIN_EMAIL) {
                setUserRole("hr");
                sessionStorage.setItem(ROLE_KEY, "hr");
                setRoleLoading(false);
                return;
            }

            // ── Regular users ────────────────────────────────────────────
            const cached = sessionStorage.getItem(ROLE_KEY);

            if (cached) {
                // Cached role gives an instant answer — no loading state needed.
                setUserRole(cached);
                setRoleLoading(false);

                // Silently verify with the backend and update if it differs.
                try {
                    const { getUserRole } = await import("@/lib/interviewApi");
                    const data = await getUserRole(firebaseUser.uid);
                    if (data?.role && data.role !== cached) {
                        setUserRole(data.role);
                        sessionStorage.setItem(ROLE_KEY, data.role);
                    }
                } catch { /* non-fatal — cached value stays */ }
            } else {
                // No cache (fresh session) — must fetch before we can gate routes.
                setRoleLoading(true);
                try {
                    const { getUserRole } = await import("@/lib/interviewApi");
                    const data = await getUserRole(firebaseUser.uid);
                    const role = data?.role || null;
                    setUserRole(role);
                    if (role) sessionStorage.setItem(ROLE_KEY, role);
                } catch { /* non-fatal */ } finally {
                    setRoleLoading(false);
                }
            }
        });
        return unsubscribe;
    }, []);

    const isAuthenticated = !!user;
    const emailVerified   = user?.emailVerified ?? false;
    const isAdmin         = user?.email === ADMIN_EMAIL;

    const updateUserProfile = async ({ displayName, photoURL }) => {
        if (!auth.currentUser) return;
        await updateProfile(auth.currentUser, { displayName, photoURL });
        setUser({ ...auth.currentUser });
    };

    const updateUserEmail = async (newEmail) => {
        if (!auth.currentUser) return;
        await updateEmail(auth.currentUser, newEmail);
        setUser({ ...auth.currentUser });
    };

    const refreshUser = async () => {
        if (!auth.currentUser) return;
        await reload(auth.currentUser);
        setUser({ ...auth.currentUser });
    };

    const logout = async () => {
        sessionStorage.removeItem(ROLE_KEY);
        setUserRole(null);
        await signOut(auth);
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                loading,
                isAuthenticated,
                emailVerified,
                userRole,
                roleLoading,
                isAdmin,
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
