import type { ServerEnvironment, ServerSshAuthMethod, ServerStatus } from '../types/server';

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

export const environmentStyles: Record<ServerEnvironment, string> = {
  development: 'bg-sky-50 text-sky-700 ring-sky-200',
  staging: 'bg-violet-50 text-violet-700 ring-violet-200',
  production: 'bg-rose-50 text-rose-700 ring-rose-200',
  testing: 'bg-teal-50 text-teal-700 ring-teal-200',
  lab: 'bg-amber-50 text-amber-700 ring-amber-200',
};

export function formatLabel(value: string): string {
  return value
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
