import type { JobStatus } from '../types/job';

export function formatDateTime(value: string | null): string {
  if (!value) {
    return 'Not started';
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function jobStatusLabel(status: JobStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}
