import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getMe, oidcLogout } from "./api";

const AuthContext = createContext(null);

// Dev-only auth bypass. Set VITE_BYPASS_AUTH=true in frontend/.env.local to
// skip the login screen and use a mocked admin user without a backend.
const BYPASS_AUTH = import.meta.env.VITE_BYPASS_AUTH === "true";

const MOCK_USER = {
  id: "dev-user",
  username: "dev",
  email: "dev@lisa.local",
  role: "admin",
};

// Authentication is Keycloak only: the session lives in an HttpOnly cookie set
// by the backend, so the only thing to do here is ask who the user is.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    if (BYPASS_AUTH) {
      setUser(MOCK_USER);
      setLoading(false);
      return;
    }

    getMe()
      .then((me) => {
        if (active) setUser(me);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo(() => {
    const signOut = async () => {
      setUser(null);
      if (BYPASS_AUTH) return;
      try {
        // Ends the backend session, then Keycloak's own.
        window.location.href = await oidcLogout();
      } catch {
        window.location.href = "/login";
      }
    };
    return {
      user,
      loading,
      isAuthenticated: !!user,
      isAdmin: user?.role === "admin",
      signOut,
    };
  }, [user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
