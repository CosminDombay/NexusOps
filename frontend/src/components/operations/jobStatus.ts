const failedStatuses = new Set(['failed', 'cancelled', 'stale']);

export function isFailedJobStatus(status: string): boolean {
  return failedStatuses.has(status.toLowerCase());
}
