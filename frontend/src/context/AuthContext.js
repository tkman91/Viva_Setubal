import { createContext, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      // ignore
    }
    setUser(null);
  };

  const can = (module) => {
    if (!user) return false;
    if (user.is_admin) return true;
    return (user.permissions || []).includes(module);
  };

  const isAdmin = !!user && !!user.is_admin;
  const canManage = (module) => {
    if (!user) return false;
    if (user.is_admin) return true;
    return !!user.is_supervisor && (user.permissions || []).includes(module);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, can, isAdmin, canManage, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
