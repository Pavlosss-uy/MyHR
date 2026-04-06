import { createContext, useContext, useState, useEffect } from "react";

const AuthContext = createContext(null);

const AUTH_STORAGE_KEY = "intervai_user";

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(() => {
        try {
            const stored = localStorage.getItem(AUTH_STORAGE_KEY);
            return stored ? JSON.parse(stored) : null;
        } catch {
            return null;
        }
    });

    const isAuthenticated = !!user;

    const login = (userData) => {
        // userData: { name, email, picture?, provider }
        setUser(userData);
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(userData));
    };

    const logout = () => {
        setUser(null);
        localStorage.removeItem(AUTH_STORAGE_KEY);
        sessionStorage.removeItem("google_user");
        sessionStorage.removeItem("linkedin_auth_code");
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};
