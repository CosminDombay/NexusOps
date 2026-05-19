import type { AuthTokens, AuthUser } from '../types/auth';

const ACCESS_TOKEN_KEY = 'nexusops.accessToken';
const REFRESH_TOKEN_KEY = 'nexusops.refreshToken';
const USER_KEY = 'nexusops.user';
const legacyStorage = localStorage;
const tokenStorage = sessionStorage;

function clearLegacyAuth(): void {
  legacyStorage.removeItem(ACCESS_TOKEN_KEY);
  legacyStorage.removeItem(REFRESH_TOKEN_KEY);
  legacyStorage.removeItem(USER_KEY);
}

export function getStoredAccessToken(): string | null {
  clearLegacyAuth();
  return tokenStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken(): string | null {
  clearLegacyAuth();
  return tokenStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  clearLegacyAuth();
  const value = tokenStorage.getItem(USER_KEY);
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value) as AuthUser;
  } catch {
    clearStoredAuth();
    return null;
  }
}

export function storeAuth(tokens: AuthTokens, user: AuthUser): void {
  clearLegacyAuth();
  tokenStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  tokenStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  tokenStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearStoredAuth(): void {
  clearLegacyAuth();
  tokenStorage.removeItem(ACCESS_TOKEN_KEY);
  tokenStorage.removeItem(REFRESH_TOKEN_KEY);
  tokenStorage.removeItem(USER_KEY);
}
