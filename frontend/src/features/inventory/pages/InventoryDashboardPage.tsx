import { Database, Network, ServerIcon } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { CreateServerForm } from '../components/CreateServerForm';
import { ServerList } from '../components/ServerList';
import { useServers } from '../hooks/useServers';

export function InventoryDashboardPage() {
  const {
    servers,
    isLoading,
    isCreating,
    error,
    createError,
    mutationError,
    isCheckingHealth,
    refreshServers,
    addServer,
    editServer,
    removeServer,
    archiveInventoryServer,
    refreshHealth,
    clearCreateError,
    clearMutationError,
  } = useServers();

  const onlineServers = servers.filter((server) => server.last_health_status === 'online').length;
  const productionServers = servers.filter((server) => server.environment === 'production').length;

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

      <CreateServerForm
        apiError={createError}
        isSubmitting={isCreating}
        onFieldChange={clearCreateError}
        onSubmit={addServer}
      />

      <ServerList
        error={error}
        isLoading={isLoading}
        mutationError={mutationError}
        servers={servers}
        onArchive={archiveInventoryServer}
        onClearMutationError={clearMutationError}
        onDelete={removeServer}
        onEdit={editServer}
        onHealthCheck={refreshHealth}
        isCheckingHealth={isCheckingHealth}
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
