import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

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
