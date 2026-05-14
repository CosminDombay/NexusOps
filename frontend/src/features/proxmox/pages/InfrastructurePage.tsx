import { AlertCircle, GitCompareArrows, RefreshCw } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { NodeCards } from '../components/NodeCards';
import { SummaryCards } from '../components/SummaryCards';
import { VmTable } from '../components/VmTable';
import { useProxmoxDashboard } from '../hooks/useProxmoxDashboard';
import type { ProxmoxVm, ProxmoxVmAction } from '../types/proxmox';
import { titleCase } from '../utils/format';

export function InfrastructurePage() {
  const {
    dashboard,
    isLoading,
    error,
    actionByVmId,
    notification,
    refreshDashboard,
    runAction,
    importVm,
    reconcileInventory,
    clearNotification,
  } = useProxmoxDashboard();

  function handleVmAction(vm: ProxmoxVm, action: ProxmoxVmAction) {
    if (action !== 'start') {
      const confirmed = window.confirm(
        `${titleCase(action)} VM ${vm.name} (${vm.vm_id}) on ${vm.node}?`,
      );

      if (!confirmed) {
        return;
      }
    }

    void runAction(vm.vm_id, action);
  }

  function handleImportVm(vm: ProxmoxVm) {
    const ipAddress = window.prompt('Inventory IP address for this VM', vm.ip_address ?? '');
    if (!ipAddress) {
      return;
    }
    const sshUsername = window.prompt('SSH username', 'ubuntu');
    if (!sshUsername) {
      return;
    }

    void importVm({
      vm_id: vm.vm_id,
      node: vm.node,
      vm_type: vm.type,
      hostname: vm.name,
      ip_address: ipAddress.trim(),
      operating_system: 'cloud-init Linux',
      environment: 'lab',
      provider: 'proxmox',
      ssh_port: 22,
      ssh_username: sshUsername.trim(),
      ssh_auth_method: 'key',
      ssh_password: null,
      ssh_private_key_path: null,
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Infrastructure"
        description="Read-only Proxmox cluster visibility for nodes, guests, and current resource state."
      />

      {isLoading ? <LoadingState /> : null}
      {!isLoading && error ? <ErrorState error={error} onRetry={refreshDashboard} /> : null}
      {!isLoading && !error && dashboard ? (
        <>
          {notification ? (
            <Notification
              message={notification.message}
              tone={notification.tone}
              onDismiss={clearNotification}
            />
          ) : null}
          <div className="flex justify-end">
            <button
              className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
              type="button"
              onClick={() => void reconcileInventory()}
            >
              <GitCompareArrows className="h-4 w-4" aria-hidden="true" />
              Reconcile Inventory
            </button>
          </div>
          <SummaryCards summary={dashboard.summary} />
          <NodeCards nodes={dashboard.nodes} />
          <VmTable
            actionByVmId={actionByVmId}
            vms={dashboard.vms}
            onAction={handleVmAction}
            onImport={handleImportVm}
          />
        </>
      ) : null}
    </div>
  );
}

function Notification({
  message,
  tone,
  onDismiss,
}: {
  message: string;
  tone: 'success' | 'error';
  onDismiss: () => void;
}) {
  const className =
    tone === 'success'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
      : 'border-rose-200 bg-rose-50 text-rose-800';

  return (
    <div className={`flex items-center justify-between gap-4 rounded-lg border px-4 py-3 ${className}`}>
      <p className="text-sm font-medium">{message}</p>
      <button className="text-sm font-semibold underline-offset-2 hover:underline" type="button" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-28 animate-pulse rounded-lg bg-zinc-100" />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-lg bg-zinc-100" />
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-rose-800">
      <div className="flex gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        <div>
          <h3 className="font-semibold">Proxmox state could not be loaded</h3>
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
