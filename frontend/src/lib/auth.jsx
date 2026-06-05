import { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  getMe,
  getToken,
  login as apiLogin,
  logout as apiLogout,
} from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then((me) => {
        if (active) setUser(me);
      })
      .catch(() => {
        if (active) {
          apiLogout();
          setUser(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo(() => {
    const signIn = async (username, password) => {
      await apiLogin({ username, password });
      const me = await getMe();
      setUser(me);
      return me;
    };
    const signOut = () => {
      apiLogout();
      setUser(null);
    };
    return {
      user,
      loading,
      isAuthenticated: !!user,
      isAdmin: user?.role === "admin",
      signIn,
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
