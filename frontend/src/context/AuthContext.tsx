import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import * as authApi from '../api/auth';
import { TOKEN_STORAGE_KEY } from '../api/client';
import type { LoginRequest, User, UserCreate } from '../api/types';

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  login: (data: LoginRequest) => Promise<void>;
  signup: (data: UserCreate) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => {
    const oauthToken = new URLSearchParams(window.location.search).get('token');
    if (oauthToken) {
      localStorage.setItem(TOKEN_STORAGE_KEY, oauthToken);
      return oauthToken;
    }
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  });
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (token && window.location.search.includes('token=')) {
      const params = new URLSearchParams(window.location.search);
      params.delete('token');
      const query = params.toString();
      const cleanUrl = window.location.pathname + (query ? `?${query}` : '');
      window.history.replaceState({}, document.title, cleanUrl);
    }
    setIsLoading(false);
  }, [token]);

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    let cancelled = false;
    authApi
      .getMe()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const persistToken = useCallback((next: string) => {
    localStorage.setItem(TOKEN_STORAGE_KEY, next);
    setToken(next);
  }, []);

  const login = useCallback(
    async (data: LoginRequest) => {
      const { access_token } = await authApi.login(data);
      persistToken(access_token);
    },
    [persistToken],
  );

  const signup = useCallback(
    async (data: UserCreate) => {
      await authApi.signup(data);
      const { access_token } = await authApi.login({
        identifier: data.email,
        password: data.password,
      });
      persistToken(access_token);
    },
    [persistToken],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
  }, []);

  const value = useMemo(
    () => ({ isAuthenticated: token !== null, isLoading, user, login, signup, logout }),
    [token, isLoading, user, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}