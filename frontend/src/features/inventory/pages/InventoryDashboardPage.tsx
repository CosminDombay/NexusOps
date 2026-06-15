import { useEffect, useMemo, useState } from 'react';
import { Database, Network, Plus, ServerIcon } from 'lucide-react';

import { ContextDrawer } from '../../../components/ContextDrawer';
import { PageHeader } from '../../../components/layout/PageHeader';
import { SearchField } from '../../../components/search/SearchField';
import { matchesSearch } from '../../../lib/search/match';
import { CreateServerForm } from '../components/CreateServerForm';
import { ServerList } from '../components/ServerList';
import { useServers } from '../hooks/useServers';
import { listIntegrations } from '../../settings/api/integrationsApi';
import type { Integration } from '../../settings/types/integration';

export function InventoryDashboardPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [search, setSearch] = useState('');
  const {
    servers,
    isLoading,
    isCreating,
    error,
    createError,
    mutationError,
    isCheckingHealth,
    isRunningVmLifecycleAction,
    includeInactive,
    setIncludeInactive,
    integrationFilter,
    setIntegrationFilter,
    clusterFilter,
    setClusterFilter,
    refreshServers,
    addServer,
    editServer,
    removeServer,
    archiveInventoryServer,
    decommissionInventoryServer,
    restoreInventoryServer,
    unmanageInventoryServer,
    refreshHealth,
    runVmLifecycleAction,
    clearCreateError,
    clearMutationError,
  } = useServers();

  useEffect(() => {
    listIntegrations()
      .then((items) =>
        setIntegrations(
          items.filter((integration) => integration.type === 'infrastructure_provider'),
        ),
      )
      .catch(() => setIntegrations([]));
  }, []);

  const onlineServers = servers.filter((server) => server.last_health_status === 'online').length;
  const productionServers = servers.filter((server) => server.environment === 'production').length;
  const clusterOptions = useMemo(
    () =>
      Array.from(
        new Set(
          servers
            .map((server) => server.provider_node)
            .filter((value): value is string => Boolean(value)),
        ),
      ).sort(),
    [servers],
  );
  const filteredServers = useMemo(
    () =>
      servers.filter((server) =>
        matchesSearch(search, [
          server.hostname,
          server.ip_address,
          server.operating_system,
          server.environment,
          server.provider,
          server.provider_node,
          server.node_type,
          server.lifecycle_state,
          server.management_state,
          server.sync_state,
          server.tags,
        ]),
      ),
    [search, servers],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Server Inventory"
        description="Registered Linux servers, connection metadata, provider placement, and lifecycle state."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard icon={ServerIcon} label="Total servers" value={servers.length.toString()} />
        <MetricCard icon={Network} label="Online hosts" value={onlineServers.toString()} />
        <MetricCard icon={Database} label="Production" value={productionServers.toString()} />
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-1 flex-wrap gap-2">
          <SearchField
            className="min-w-64 flex-1"
            placeholder="Search hosts, IPs, providers..."
            value={search}
            onChange={setSearch}
          />
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 shadow-sm"
            value={integrationFilter}
            onChange={(event) => setIntegrationFilter(event.target.value)}
          >
            <option value="">All integrations</option>
            {integrations.map((integration) => (
              <option key={integration.id} value={integration.id}>
                {integration.name}
              </option>
            ))}
          </select>
          <select
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 shadow-sm"
            value={clusterFilter}
            onChange={(event) => setClusterFilter(event.target.value)}
          >
            <option value="">All clusters/groups</option>
            {clusterOptions.map((cluster) => (
              <option key={cluster} value={cluster}>
                {cluster}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <label className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 shadow-sm">
            <input
              checked={includeInactive}
              type="checkbox"
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            Show inactive
          </label>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50"
            type="button"
            onClick={() => setIsCreateOpen(true)}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Import existing host
          </button>
        </div>
      </div>

      <ContextDrawer
        description="Manual import is for managed bare-metal nodes and externally provisioned systems."
        isOpen={isCreateOpen}
        title="Import Existing Host"
        width="lg"
        onClose={() => setIsCreateOpen(false)}
      >
        <CreateServerForm
          apiError={createError}
          isSubmitting={isCreating}
          onFieldChange={clearCreateError}
          onSubmit={async (payload) => {
            const created = await addServer(payload);
            if (created) {
              setIsCreateOpen(false);
            }
            return created;
          }}
        />
      </ContextDrawer>

      <ServerList
        error={error}
        isLoading={isLoading}
        mutationError={mutationError}
        servers={filteredServers}
        onArchive={archiveInventoryServer}
        onDecommission={decommissionInventoryServer}
        onRestore={restoreInventoryServer}
        onUnmanage={unmanageInventoryServer}
        onClearMutationError={clearMutationError}
        onDelete={removeServer}
        onEdit={editServer}
        onHealthCheck={refreshHealth}
        onVmLifecycleAction={runVmLifecycleAction}
        isCheckingHealth={isCheckingHealth}
        isRunningVmLifecycleAction={isRunningVmLifecycleAction}
        onRetry={refreshServers}
      />
    </div>
  );
}

type MetricCardProps = {
  icon: typeof ServerIcon;
  label: string;
  value: string;
};

function MetricCard({ icon: Icon, label, value }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-zinc-500">{label}</p>
          <p className="mt-2 text-3xl font-semibold text-zinc-950">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-zinc-950 text-white">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
