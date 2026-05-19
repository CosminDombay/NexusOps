import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, Archive, CheckSquare, Pencil, Play, Power, RefreshCw, RotateCcw, RotateCw, ServerIcon, Trash2 } from 'lucide-react';

import type { ProxmoxVmAction } from '../../proxmox/types/proxmox';
import type { Server, UpdateServerPayload } from '../types/server';
import { formatLabel } from '../utils/options';
import { EnvironmentBadge, HealthBadge, LifecycleBadge, ManagementBadge, NodeTypeBadge, SyncBadge } from './ServerBadges';
import { EditServerModal } from './EditServerModal';

type ServerListProps = {
  servers: Server[];
  isLoading: boolean;
  error: string | null;
  mutationError: string | null;
  onRetry: () => void;
  onEdit: (serverId: string, payload: UpdateServerPayload) => Promise<boolean>;
  onDelete: (serverId: string) => Promise<boolean>;
  onArchive: (serverId: string) => Promise<boolean>;
  onDecommission: (serverId: string) => Promise<boolean>;
  onRestore: (serverId: string) => Promise<boolean>;
  onUnmanage: (serverId: string) => Promise<boolean>;
  onHealthCheck: (serverIds?: string[]) => Promise<boolean>;
  onVmLifecycleAction: (serverIds: string[], action: ProxmoxVmAction) => Promise<boolean>;
  isCheckingHealth: boolean;
  isRunningVmLifecycleAction: boolean;
  onClearMutationError: () => void;
};

export function ServerList({
  servers,
  isLoading,
  error,
  mutationError,
  onRetry,
  onEdit,
  onDelete,
  onArchive,
  onDecommission,
  onRestore,
  onUnmanage,
  onHealthCheck,
  onVmLifecycleAction,
  isCheckingHealth,
  isRunningVmLifecycleAction,
  onClearMutationError,
}: ServerListProps) {
  const [editingServer, setEditingServer] = useState<Server | null>(null);
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    const serverIds = new Set(servers.map((server) => server.id));
    setSelectedServerIds((current) => current.filter((serverId) => serverIds.has(serverId)));
  }, [servers]);

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

  const selectedServers = servers.filter((server) => selectedServerIds.includes(server.id));
  const selectedLifecycleTargets = selectedServers.filter(hasInventoryVmId);
  const allServersSelected = selectedServerIds.length === servers.length;
  const hasSelection = selectedServerIds.length > 0;

  function toggleAllServers(checked: boolean) {
    setSelectedServerIds(checked ? servers.map((server) => server.id) : []);
  }

  async function runSelectedLifecycleAction(action: ProxmoxVmAction) {
    if (!hasSelection) {
      return;
    }

    if (action !== 'start') {
      const actionLabel = action === 'shutdown' ? 'shut down' : action;
      const confirmed = window.confirm(
        `${actionLabel.charAt(0).toUpperCase() + actionLabel.slice(1)} ${selectedServerIds.length} selected inventory host(s)?`,
      );
      if (!confirmed) {
        return;
      }
    }

    const success = await onVmLifecycleAction(selectedServerIds, action);
    if (success) {
      setSelectedServerIds([]);
    }
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-zinc-200 px-5 py-4">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">Registered servers</h3>
          <p className="mt-1 text-sm text-zinc-500">
            {servers.length} hosts tracked by inventory
            {hasSelection ? ` - ${selectedServerIds.length} selected` : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {hasSelection ? (
            <div className="flex flex-wrap gap-2">
              <LifecycleActionButton
                action="start"
                count={selectedLifecycleTargets.length}
                disabled={isRunningVmLifecycleAction || selectedLifecycleTargets.length === 0}
                icon={Play}
                label="Start"
                onClick={runSelectedLifecycleAction}
              />
              <LifecycleActionButton
                action="shutdown"
                count={selectedLifecycleTargets.length}
                disabled={isRunningVmLifecycleAction || selectedLifecycleTargets.length === 0}
                icon={Power}
                label="Shutdown"
                onClick={runSelectedLifecycleAction}
              />
              <LifecycleActionButton
                action="reboot"
                count={selectedLifecycleTargets.length}
                disabled={isRunningVmLifecycleAction || selectedLifecycleTargets.length === 0}
                icon={RotateCw}
                label="Reboot"
                onClick={runSelectedLifecycleAction}
              />
              <LifecycleActionButton
                action="stop"
                count={selectedLifecycleTargets.length}
                disabled={isRunningVmLifecycleAction || selectedLifecycleTargets.length === 0}
                icon={Power}
                label="Stop"
                onClick={runSelectedLifecycleAction}
                variant="danger"
              />
            </div>
          ) : null}
          <button
            className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            disabled={isCheckingHealth || isRunningVmLifecycleAction}
            onClick={() => void onHealthCheck(selectedServerIds.length ? selectedServerIds : undefined)}
          >
            <CheckSquare className="h-4 w-4" aria-hidden="true" />
            {isCheckingHealth ? 'Checking...' : selectedServerIds.length ? `Check ${selectedServerIds.length}` : 'Check health'}
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
            type="button"
            onClick={onRetry}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        </div>
      </div>
      {mutationError ? (
        <div className="border-b border-rose-200 bg-rose-50 px-5 py-3 text-sm text-rose-800">
          <div className="flex items-center justify-between gap-3">
            <span>{mutationError}</span>
            <button className="font-semibold underline-offset-2 hover:underline" type="button" onClick={onClearMutationError}>
              Dismiss
            </button>
          </div>
        </div>
      ) : null}

      <div className="hidden overflow-x-auto lg:block">
        <table className="min-w-full divide-y divide-zinc-200">
          <thead className="bg-zinc-50">
            <tr>
              <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-normal text-zinc-500">
                <input
                  aria-label={allServersSelected ? 'Clear selected servers' : 'Select all servers'}
                  checked={allServersSelected}
                  className="h-4 w-4 rounded border-zinc-300 text-zinc-950 focus:ring-zinc-950"
                  type="checkbox"
                  onChange={(event) => toggleAllServers(event.target.checked)}
                />
              </th>
              {['Hostname', 'Type', 'IP address', 'Environment', 'Provider', 'Lifecycle', 'Mgmt', 'Sync', 'Health', 'Last checked', 'Actions'].map((heading) => (
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
                  <input
                    aria-label={`Select ${server.hostname}`}
                    checked={selectedServerIds.includes(server.id)}
                    className="h-4 w-4 rounded border-zinc-300 text-zinc-950 focus:ring-zinc-950"
                    type="checkbox"
                    onChange={(event) => {
                      setSelectedServerIds((current) =>
                        event.target.checked
                          ? [...current, server.id]
                          : current.filter((serverId) => serverId !== server.id),
                      );
                    }}
                  />
                </td>
                <td className="px-5 py-4">
                  <Link className="font-medium text-zinc-950 hover:text-zinc-700" to={`/inventory/${server.id}`}>
                    {server.hostname}
                  </Link>
                  <div className="mt-1 text-xs text-zinc-500">{server.operating_system}</div>
                </td>
                <td className="px-5 py-4">
                  <NodeTypeBadge nodeType={server.node_type} />
                </td>
                <td className="px-5 py-4 text-sm font-mono text-zinc-700">{server.ip_address}</td>
                <td className="px-5 py-4">
                  <EnvironmentBadge environment={server.environment} />
                </td>
                <td className="px-5 py-4 text-sm text-zinc-700">{formatLabel(server.provider)}</td>
                <td className="px-5 py-4">
                  <LifecycleBadge state={server.lifecycle_state} />
                </td>
                <td className="px-5 py-4">
                  <ManagementBadge state={server.management_state} />
                </td>
                <td className="px-5 py-4">
                  <SyncBadge status={server.sync_state} />
                </td>
                <td className="px-5 py-4">
                  <HealthBadge status={server.last_health_status} />
                </td>
                <td className="px-5 py-4 text-xs text-zinc-500">
                  {formatTimestamp(server.last_health_check_at)}
                </td>
                <td className="px-5 py-4">
                  <ServerActions
                    server={server}
                    onOpenEdit={() => {
                      setEditingServer(server);
                      setSaveError(null);
                    }}
                    onArchive={onArchive}
                    onDecommission={onDecommission}
                    onDelete={onDelete}
                    onRestore={onRestore}
                    onUnmanage={onUnmanage}
                  />
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
              <div className="flex items-start gap-3">
                <input
                  aria-label={`Select ${server.hostname}`}
                  checked={selectedServerIds.includes(server.id)}
                  className="mt-1 h-4 w-4 rounded border-zinc-300 text-zinc-950 focus:ring-zinc-950"
                  type="checkbox"
                  onChange={(event) => {
                    setSelectedServerIds((current) =>
                      event.target.checked
                        ? [...current, server.id]
                        : current.filter((serverId) => serverId !== server.id),
                    );
                  }}
                />
                <div>
                  <Link className="font-semibold text-zinc-950 hover:text-zinc-700" to={`/inventory/${server.id}`}>
                    {server.hostname}
                  </Link>
                  <p className="mt-1 font-mono text-sm text-zinc-600">{server.ip_address}</p>
                </div>
              </div>
              <HealthBadge status={server.last_health_status} />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <EnvironmentBadge environment={server.environment} />
              <NodeTypeBadge nodeType={server.node_type} />
              <LifecycleBadge state={server.lifecycle_state} />
              <ManagementBadge state={server.management_state} />
              <SyncBadge status={server.sync_state} />
              <HealthBadge status={server.last_health_status} />
              <span className="inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
                {formatLabel(server.provider)}
              </span>
              <span className="inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
                {server.ssh_auth_method === 'password' ? 'Password' : 'SSH Key'}
              </span>
            </div>
            <p className="mt-3 text-sm text-zinc-500">{server.operating_system}</p>
            <p className="mt-1 text-xs text-zinc-500">Last checked: {formatTimestamp(server.last_health_check_at)}</p>
            <div className="mt-4">
              <ServerActions
                server={server}
                onOpenEdit={() => {
                  setEditingServer(server);
                  setSaveError(null);
                }}
                onArchive={onArchive}
                onDecommission={onDecommission}
                onDelete={onDelete}
                onRestore={onRestore}
                onUnmanage={onUnmanage}
              />
            </div>
          </article>
        ))}
      </div>

      {/* Edit Modal */}
      {editingServer && (
        <EditServerModal
          server={editingServer}
          isOpen={true}
          onClose={() => {
            setEditingServer(null);
            setSaveError(null);
          }}
          onSave={async (payload) => {
            setIsSaving(true);
            setSaveError(null);
            try {
              const success = await onEdit(editingServer.id, payload);
              if (success) {
                setEditingServer(null);
              }
            } catch (err) {
              setSaveError(err instanceof Error ? err.message : 'Save failed');
            } finally {
              setIsSaving(false);
            }
          }}
          isSaving={isSaving}
          error={saveError}
        />
      )}
    </section>
  );
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return 'Never';
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value));
}

function hasInventoryVmId(server: Server): boolean {
  if (server.provider?.toLowerCase() !== 'proxmox') {
    return false;
  }

  const rawVmId = server.vmid ?? server.external_id;
  if (rawVmId === null || rawVmId === undefined || rawVmId === '') {
    return false;
  }

  const vmId = Number(rawVmId);
  return Number.isInteger(vmId) && vmId > 0;
}

function LifecycleActionButton({
  action,
  count,
  disabled,
  icon: Icon,
  label,
  onClick,
  variant = 'default',
}: {
  action: ProxmoxVmAction;
  count: number;
  disabled: boolean;
  icon: typeof Play;
  label: string;
  onClick: (action: ProxmoxVmAction) => Promise<void>;
  variant?: 'default' | 'danger';
}) {
  const buttonClass =
    variant === 'danger'
      ? 'border-rose-400 bg-white text-rose-700 hover:bg-rose-50'
      : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50';

  return (
    <button
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${buttonClass}`}
      type="button"
      disabled={disabled}
      title={count === 0 ? 'Selected hosts need Proxmox VMIDs before lifecycle actions can run.' : undefined}
      onClick={() => void onClick(action)}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label} {count}
    </button>
  );
}

function ServerActions({
  server,
  onOpenEdit,
  onArchive,
  onDecommission,
  onDelete,
  onRestore,
  onUnmanage,
}: {
  server: Server;
  onOpenEdit: () => void;
  onArchive: (serverId: string) => Promise<boolean>;
  onDecommission: (serverId: string) => Promise<boolean>;
  onDelete: (serverId: string) => Promise<boolean>;
  onRestore: (serverId: string) => Promise<boolean>;
  onUnmanage: (serverId: string) => Promise<boolean>;
}) {
  const inactive =
    server.lifecycle_state === 'archived' ||
    server.lifecycle_state === 'decommissioned' ||
    server.lifecycle_state === 'deleted';

  async function archiveServer() {
    if (window.confirm(`Archive ${server.hostname}? Jobs will no longer target this inventory record.`)) {
      await onArchive(server.id);
    }
  }

  async function decommissionServer() {
    if (window.confirm(`Decommission ${server.hostname}? The node will leave active operational flows but remain historically queryable.`)) {
      await onDecommission(server.id);
    }
  }

  async function restoreServer() {
    if (window.confirm(`Restore ${server.hostname} to active managed inventory?`)) {
      await onRestore(server.id);
    }
  }

  async function unmanageServer() {
    if (window.confirm(`Mark ${server.hostname} as unmanaged? It will stay visible but jobs and remote access will no longer target it.`)) {
      await onUnmanage(server.id);
    }
  }

  async function deleteServer() {
    if (window.confirm(`Delete inventory record ${server.hostname}? This will not destroy the Proxmox VM.`)) {
      await onDelete(server.id);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {inactive ? (
        <button
          className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-50"
          type="button"
          onClick={restoreServer}
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
          Restore
        </button>
      ) : (
        <>
          <button
            className="inline-flex items-center gap-1.5 rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-50"
            type="button"
            onClick={onOpenEdit}
          >
            <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
            Edit
          </button>
          {server.management_state === 'managed' ? (
            <button
              className="inline-flex items-center gap-1.5 rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-50"
              type="button"
              onClick={unmanageServer}
            >
              Unmanage
            </button>
          ) : (
            <button
              className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-50"
              type="button"
              onClick={restoreServer}
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Manage
            </button>
          )}
          <button
            className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-amber-700 transition hover:bg-amber-50"
            type="button"
            onClick={archiveServer}
          >
            <Archive className="h-3.5 w-3.5" aria-hidden="true" />
            Archive
          </button>
          <button
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
            type="button"
            onClick={decommissionServer}
          >
            Decommission
          </button>
        </>
      )}
      <button
        className="inline-flex items-center gap-1.5 rounded-md border border-rose-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-50"
        type="button"
        onClick={deleteServer}
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
        Delete
      </button>
    </div>
  );
}
