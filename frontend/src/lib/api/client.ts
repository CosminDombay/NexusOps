import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

import {
  clearStoredAuth,
  getStoredAccessToken,
  getStoredRefreshToken,
  storeAuth,
} from '../../features/auth/api/tokenStorage';
import type { LoginResponse } from '../../features/auth/types/auth';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

const refreshClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

let refreshPromise: Promise<LoginResponse> | null = null;

type RetriableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

apiClient.interceptors.request.use((config) => {
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetriableRequestConfig | undefined;
    const status = error.response?.status;
    const isAuthEndpoint = originalRequest?.url?.startsWith('/auth/');

    if (status !== 401 || !originalRequest || originalRequest._retry || isAuthEndpoint) {
      if (status === 401) {
        clearStoredAuth();
        if (window.location.pathname !== '/login') {
          window.location.assign('/login');
        }
      }
      return Promise.reject(error);
    }

    const refreshToken = getStoredRefreshToken();
    if (!refreshToken) {
      clearStoredAuth();
      window.location.assign('/login');
      return Promise.reject(error);
    }

    originalRequest._retry = true;
    refreshPromise ??= refreshClient
      .post<LoginResponse>('/auth/refresh', { refresh_token: refreshToken })
      .then((response) => {
        storeAuth(response.data, response.data.user);
        return response.data;
      })
      .finally(() => {
        refreshPromise = null;
      });

    try {
      const refreshed = await refreshPromise;
      originalRequest.headers.Authorization = `Bearer ${refreshed.access_token}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      clearStoredAuth();
      if (window.location.pathname !== '/login') {
        window.location.assign('/login');
      }
      return Promise.reject(refreshError);
    }
  },
);

type ApiValidationDetail = {
  loc?: Array<string | number>;
  msg?: string;
};

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;

    if (typeof detail === 'string') {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item: ApiValidationDetail) => {
          const field = item.loc?.filter((part) => part !== 'body').join('.');
          return field && item.msg ? `${field}: ${item.msg}` : item.msg;
        })
        .filter(Boolean)
        .join(' ');
    }

    if (error.response?.status) {
      return `Request failed with status ${error.response.status}.`;
    }

    if (error.request) {
      return 'Unable to reach the NexusOps API. Check that the backend is running and CORS is configured.';
    }
  }

  return error instanceof Error ? error.message : 'Something went wrong while contacting the API.';
}
