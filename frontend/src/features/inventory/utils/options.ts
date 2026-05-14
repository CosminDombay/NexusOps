import type {
  InventoryLifecycleState,
  InventoryHealthStatus,
  InventorySyncStatus,
  ServerEnvironment,
  ServerSshAuthMethod,
  ServerStatus,
} from '../types/server';
import { STATE_LABELS } from '../../../lib/constants';

export const environmentOptions: Array<{ label: string; value: ServerEnvironment }> = [
  { label: 'Development', value: 'development' },
  { label: 'Staging', value: 'staging' },
  { label: 'Production', value: 'production' },
  { label: 'Testing', value: 'testing' },
  { label: 'Lab', value: 'lab' },
];

export const sshAuthMethodOptions: Array<{ label: string; value: ServerSshAuthMethod }> = [
  { label: 'SSH Key', value: 'key' },
  { label: 'Password', value: 'password' },
];

export const statusStyles: Record<ServerStatus, string> = {
  unknown: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  online: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  offline: 'bg-rose-50 text-rose-700 ring-rose-200',
  maintenance: 'bg-amber-50 text-amber-700 ring-amber-200',
};

export const lifecycleStyles: Record<InventoryLifecycleState, string> = {
  discovered: 'bg-blue-50 text-blue-700 ring-blue-200',
  managed: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  provisioned: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  unmanaged: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  archived: 'bg-stone-100 text-stone-700 ring-stone-200',
};

export const syncStyles: Record<InventorySyncStatus, string> = {
  unknown: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  synced: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  unmanaged: 'bg-amber-50 text-amber-700 ring-amber-200',
  orphaned: 'bg-rose-50 text-rose-700 ring-rose-200',
  mismatch: 'bg-orange-50 text-orange-700 ring-orange-200',
  archived: 'bg-stone-100 text-stone-700 ring-stone-200',
};

export const healthStyles: Record<InventoryHealthStatus, string> = {
  online: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  unreachable: 'bg-rose-50 text-rose-700 ring-rose-200',
  unknown: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  provisioning: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  archived: 'bg-stone-100 text-stone-700 ring-stone-200',
  sync_error: 'bg-orange-50 text-orange-700 ring-orange-200',
};

export const environmentStyles: Record<ServerEnvironment, string> = {
  development: 'bg-sky-50 text-sky-700 ring-sky-200',
  staging: 'bg-violet-50 text-violet-700 ring-violet-200',
  production: 'bg-rose-50 text-rose-700 ring-rose-200',
  testing: 'bg-teal-50 text-teal-700 ring-teal-200',
  lab: 'bg-amber-50 text-amber-700 ring-amber-200',
};

/** Format a label by splitting on delimiters and title-casing */
export function formatLabel(value?: string | null): string {
  if (!value) {
    return STATE_LABELS.get('unknown') ?? 'Unknown';
  }
  const parts = value.split(/[-_]/);
  return parts
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

/** Get style class for a status */
export function getStatusStyle(status?: ServerStatus | null): string {
  if (!status || !statusStyles[status]) {
    return statusStyles.unknown;
  }
  return statusStyles[status];
}

/** Get style class for a lifecycle state */
export function getLifecycleStyle(state?: InventoryLifecycleState | null): string {
  if (!state || !lifecycleStyles[state]) {
    return lifecycleStyles.discovered;
  }
  return lifecycleStyles[state];
}

/** Get style class for a sync status */
export function getSyncStyle(status?: InventorySyncStatus | null): string {
  if (!status || !syncStyles[status]) {
    return syncStyles.unknown;
  }
  return syncStyles[status];
}

/** Get style class for an environment */
export function getEnvironmentStyle(env?: ServerEnvironment | null): string {
  if (!env || !environmentStyles[env]) {
    return environmentStyles.lab;
  }
  return environmentStyles[env];
}
