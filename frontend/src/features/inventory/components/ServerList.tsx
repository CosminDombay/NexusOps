import { AlertCircle, RefreshCw, ServerIcon } from 'lucide-react';

import type { Server } from '../types/server';
import { formatLabel } from '../utils/options';
import { EnvironmentBadge, StatusBadge } from './ServerBadges';

type ServerListProps = {
  servers: Server[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
};

export function ServerList({ servers, isLoading, error, onRetry }: ServerListProps) {
  if (isLoading) {
    return (
      <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="h-14 animate-pulse rounded-md bg-zinc-100" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-rose-800">
        <div className="flex gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
          <div>
            <h3 className="font-semibold">Inventory could not be loaded</h3>
            <p className="mt-1 text-sm">{error}</p>
            <button
              className="mt-4 inline-flex items-center gap-2 rounded-md bg-rose-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-rose-800"
              type="button"
              onClick={onRetry}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (servers.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-8 text-center shadow-sm">
        <ServerIcon className="mx-auto h-8 w-8 text-zinc-400" aria-hidden="true" />
        <h3 className="mt-3 text-base font-semibold text-zinc-950">No servers registered</h3>
        <p className="mt-1 text-sm text-zinc-500">Create the first inventory record to start building the fleet view.</p>
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-zinc-200 px-5 py-4">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">Registered servers</h3>
          <p className="mt-1 text-sm text-zinc-500">{servers.length} hosts tracked by inventory</p>
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={onRetry}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>

      <div className="hidden overflow-x-auto lg:block">
        <table className="min-w-full divide-y divide-zinc-200">
          <thead className="bg-zinc-50">
            <tr>
              {['Hostname', 'IP address', 'Environment', 'Provider', 'SSH auth', 'Status'].map((heading) => (
                <th key={heading} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-normal text-zinc-500">
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 bg-white">
            {servers.map((server) => (
              <tr key={server.id} className="hover:bg-zinc-50">
                <td className="px-5 py-4">
                  <div className="font-medium text-zinc-950">{server.hostname}</div>
                  <div className="mt-1 text-xs text-zinc-500">{server.operating_system}</div>
                </td>
                <td className="px-5 py-4 text-sm font-mono text-zinc-700">{server.ip_address}</td>
                <td className="px-5 py-4">
                  <EnvironmentBadge environment={server.environment} />
                </td>
                <td className="px-5 py-4 text-sm text-zinc-700">{formatLabel(server.provider)}</td>
                <td className="px-5 py-4 text-sm text-zinc-700">
                  {server.ssh_auth_method === 'password' ? 'Password' : 'SSH Key'}
                </td>
                <td className="px-5 py-4">
                  <StatusBadge status={server.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 p-4 lg:hidden">
        {servers.map((server) => (
          <article key={server.id} className="rounded-lg border border-zinc-200 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="font-semibold text-zinc-950">{server.hostname}</h4>
                <p className="mt-1 font-mono text-sm text-zinc-600">{server.ip_address}</p>
              </div>
              <StatusBadge status={server.status} />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <EnvironmentBadge environment={server.environment} />
              <span className="inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
                {formatLabel(server.provider)}
              </span>
              <span className="inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
                {server.ssh_auth_method === 'password' ? 'Password' : 'SSH Key'}
              </span>
            </div>
            <p className="mt-3 text-sm text-zinc-500">{server.operating_system}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
