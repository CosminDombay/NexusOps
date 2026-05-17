import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { getApiErrorMessage } from '../../../lib/api/client';
import { getMe, login as loginRequest, logout as logoutRequest, refreshSession } from '../api/authApi';
import {
  clearStoredAuth,
  getStoredRefreshToken,
  getStoredUser,
  storeAuth,
} from '../api/tokenStorage';
import type { AuthUser, LoginRequest } from '../types/auth';
import { AuthContext } from './authContextValue';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
  const [isRestoring, setIsRestoring] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const refreshToken = getStoredRefreshToken();
      if (!refreshToken) {
        setIsRestoring(false);
        return;
      }

      try {
        const refreshed = await refreshSession(refreshToken);
        if (cancelled) {
          return;
        }
        storeAuth(refreshed, refreshed.user);
        setUser(refreshed.user);
        const me = await getMe();
        if (!cancelled) {
          setUser(me);
          storeAuth(refreshed, me);
        }
      } catch {
        clearStoredAuth();
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsRestoring(false);
        }
      }
    }

    void restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (payload: LoginRequest) => {
    try {
      const response = await loginRequest(payload);
      storeAuth(response, response.user);
      setUser(response.user);
    } catch (error) {
      throw new Error(getApiErrorMessage(error));
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      clearStoredAuth();
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: user !== null,
      isRestoring,
      login,
      logout,
    }),
    [isRestoring, login, logout, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
