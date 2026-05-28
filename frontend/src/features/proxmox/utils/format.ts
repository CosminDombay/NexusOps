export function formatBytes(value: number | null): string {
  if (value === null || value === undefined) {
    return 'Unavailable';
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let nextValue = value;
  let unitIndex = 0;

  while (nextValue >= 1024 && unitIndex < units.length - 1) {
    nextValue /= 1024;
    unitIndex += 1;
  }

  return `${nextValue.toFixed(nextValue >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export function formatPercent(value: number | null): string {
  if (value === null || value === undefined) {
    return 'Unavailable';
  }

  return `${Math.round(value * 100)}%`;
}

export function formatUptime(seconds: number | null): string {
  if (!seconds) {
    return 'Unavailable';
  }

  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);

  if (days > 0) {
    return `${days}d ${hours}h`;
  }

  return `${hours}h`;
}

export function statusClassName(status?: string | null): string {
  if (!status) {
    return 'bg-zinc-100 text-zinc-700 ring-zinc-200';
  }

  if (status === 'online' || status === 'running') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }

  if (status === 'offline' || status === 'stopped') {
    return 'bg-zinc-100 text-zinc-700 ring-zinc-200';
  }

  return 'bg-amber-50 text-amber-700 ring-amber-200';
}

export function titleCase(value?: string | null): string {
  if (!value) {
    return 'Unknown';
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/**
 * Get a human-readable display value with fallback to Unknown.
 * Safely handles undefined, null, and empty strings.
 */
export function displayValue(value?: string | null): string {
  if (!value) {
    return 'Unknown';
  }
  return value;
}
