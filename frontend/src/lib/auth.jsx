import { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  getAuthConfig,
  getMe,
  oidcLogout,
  getToken,
  login as apiLogin,
  logout as apiLogout,
} from "./api";

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

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [provider, setProvider] = useState("local");

  useEffect(() => {
    let active = true;

    if (BYPASS_AUTH) {
      setUser(MOCK_USER);
      setLoading(false);
      return;
    }

    (async () => {
      let mode = "local";
      try {
        mode = (await getAuthConfig()).provider;
      } catch {
        /* backend unreachable: fall back to local flow */
      }
      if (!active) return;
      setProvider(mode);
      // Local mode keeps a bearer token; Keycloak mode relies on the cookie.
      if (mode === "local" && !getToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await getMe();
        if (active) setUser(me);
      } catch {
        if (active) {
          apiLogout();
          setUser(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo(() => {
    const signIn = async (username, password) => {
      if (BYPASS_AUTH) {
        setUser(MOCK_USER);
        return MOCK_USER;
      }
      await apiLogin({ username, password });
      const me = await getMe();
      setUser(me);
      return me;
    };
    const signOut = async () => {
      if (BYPASS_AUTH) {
        setUser(null);
        return;
      }
      if (provider === "keycloak") {
        setUser(null);
        try {
          window.location.href = await oidcLogout();
        } catch {
          window.location.href = "/login";
        }
        return;
      }
      apiLogout();
      setUser(null);
    };
    return {
      user,
      loading,
      isAuthenticated: !!user,
      provider,
      isAdmin: user?.role === "admin",
      signIn,
      signOut,
    };
  }, [user, loading, provider]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
