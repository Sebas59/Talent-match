import { createContext, useCallback, useContext, useEffect, useState } from "react";
import * as client from "./api.js";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    client.setSessionLostHandler(() => setUser(null));
    client.refreshSession().then((d) => { if (d) setUser(d.user); setReady(true); });
  }, []);

  const signIn = useCallback(async (email, password) => {
    const d = await client.login(email, password);
    setUser(d.user);
    return d.user;
  }, []);

  const signOut = useCallback(async () => {
    await client.logout();
    setUser(null);
  }, []);

  return <AuthCtx.Provider value={{ user, ready, signIn, signOut }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
