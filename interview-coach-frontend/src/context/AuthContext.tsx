import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import * as api from '../api/client';
import type { UserOut } from '../api/types';

interface AuthContextValue {
  isAuthenticated: boolean;
  signup: (email: string, password: string, fullName: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => !!api.getToken());

  const signup = useCallback(async (email: string, password: string, fullName: string) => {
    await api.signup(email, password, fullName);
    const token = await api.login(email, password);
    api.setToken(token.access_token);
    setIsAuthenticated(true);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const token = await api.login(email, password);
    api.setToken(token.access_token);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    api.clearToken();
    setIsAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, signup, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export type { UserOut };
