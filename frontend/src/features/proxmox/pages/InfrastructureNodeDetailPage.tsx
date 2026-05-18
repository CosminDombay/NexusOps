import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertCircle, Cpu, HardDrive, Power, RefreshCw, ServerIcon, Wrench } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { useAuth } from '../../auth/hooks/useAuth';
import { getProxmoxNodeDetail, runVmAction } from '../api/proxmoxApi';
import type { ProxmoxNodeDetail, ProxmoxVm, ProxmoxVmAction } from '../types/proxmox';
import { formatBytes, formatPercent, formatUptime, titleCase } from '../utils/format';
import { StatusBadge } from '../components/StatusBadge';
import { VmActions } from '../components/VmTable';

export function InfrastructureNodeDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [detail, setDetail] = useState<ProxmoxNodeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);
  const [actionByVmId, setActionByVmId] = useState<Record<number, ProxmoxVmAction | undefined>>({});
  const [isLoading, setIsLoading] = useState(true);
  const allowActions = user?.role === 'admin' || user?.role === 'operator';

  const refresh = useCallback(async () => {
    if (!id) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setDetail(await getProxmoxNodeDetail(id));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleVmAction(vm: ProxmoxVm, action: ProxmoxVmAction) {
    if (action !== 'start') {
      const confirmed = window.confirm(`${titleCase(action)} VM ${vm.name} (${vm.vm_id}) on ${vm.node}?`);
      if (!confirmed) {
        return;
      }
    }

    setActionByVmId((current) => ({ ...current, [vm.vm_id]: action }));
    setNotification(null);
    setError(null);
    try {
      const response = await runVmAction(vm.vm_id, action);
      setNotification({ tone: 'success', message: response.message });
      await refresh();
    } catch (requestError) {
      setNotification({ tone: 'error', message: getApiErrorMessage(requestError) });
    } finally {
      setActionByVmId((current) => {
        const next = { ...current };
        delete next[vm.vm_id];
        return next;
      });
    }
  }

  if (isLoading && !detail) {
    return <div className="h-80 animate-pulse rounded-lg bg-zinc-100" />;
  }

  if (error || !detail) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-rose-800">
        <div className="flex gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
          <div>
            <h3 className="font-semibold">Node could not be loaded</h3>
            <p className="mt-1 text-sm">{error}</p>
            <button className="mt-4 inline-flex items-center gap-2 rounded-md bg-rose-700 px-3 py-2 text-sm font-semibold text-white" type="button" onClick={() => void refresh()}>
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { node, vms } = detail;

  return (
    <div className="space-y-6">
      <PageHeader title={node.name} description="Proxmox node resources, hosted guests, and planned safe management controls." />
      {notification ? <Notification message={notification.message} tone={notification.tone} onDismiss={() => setNotification(null)} /> : null}
      <div className="flex items-center justify-between gap-3">
        <StatusBadge status={node.status} />
        <button className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={() => void refresh()}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card icon={Cpu} label="CPU" value={formatPercent(node.cpu_usage)} />
        <Card icon={HardDrive} label="Memory" value={`${formatBytes(node.memory_used)} / ${formatBytes(node.memory_total)}`} />
        <Card icon={ServerIcon} label="VMs / CTs" value={String(node.vm_count)} />
        <Card icon={Power} label="Uptime" value={formatUptime(node.uptime_seconds)} />
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Hosted Guests</h3>
          <p className="mt-1 text-sm text-zinc-500">{vms.length} guests reported by Proxmox.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-zinc-200">
            <thead className="bg-zinc-50">
              <tr>{['Name', 'VMID', 'Type', 'Status', 'IP', 'Inventory', 'Actions'].map((heading) => <th key={heading} className="px-5 py-3 text-left text-xs font-semibold uppercase text-zinc-500">{heading}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {vms.map((vm) => (
                <tr key={`${vm.node}-${vm.vm_id}`}>
                  <td className="px-5 py-4 text-sm font-semibold text-zinc-950">{vm.name}</td>
                  <td className="px-5 py-4 font-mono text-sm text-zinc-700">{vm.vm_id}</td>
                  <td className="px-5 py-4 text-sm text-zinc-700">{vm.type}</td>
                  <td className="px-5 py-4"><StatusBadge status={vm.status} /></td>
                  <td className="px-5 py-4 font-mono text-sm text-zinc-700">{vm.ip_address ?? '-'}</td>
                  <td className="px-5 py-4 text-sm">
                    {vm.inventory_server_id ? <Link className="font-semibold text-zinc-800 hover:text-zinc-950" to={`/inventory/${vm.inventory_server_id}`}>{vm.inventory_hostname}</Link> : titleCase(vm.inventory_sync_status)}
                  </td>
                  <td className="px-5 py-4">
                    <VmActions
                      activeAction={actionByVmId[vm.vm_id]}
                      allowActions={allowActions}
                      allowImport={false}
                      vm={vm}
                      onAction={(targetVm, action) => void handleVmAction(targetVm, action)}
                      onImport={() => undefined}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Planned Node Controls</h3>
        <div className="mt-4 flex flex-wrap gap-2">
          {detail.placeholders.map((item) => (
            <span key={item} className="inline-flex items-center gap-2 rounded-full bg-zinc-100 px-3 py-1 text-xs font-semibold text-zinc-700 ring-1 ring-inset ring-zinc-200">
              <Wrench className="h-3.5 w-3.5" aria-hidden="true" />
              {titleCase(item.replace(/_/g, ' '))}
            </span>
          ))}
        </div>
      </section>
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
      ? 'border-emerald-400/30 bg-emerald-950/40 text-emerald-100'
      : 'border-rose-400/30 bg-rose-950/50 text-rose-100';

  return (
    <div className={`flex items-center justify-between gap-4 rounded-lg border px-4 py-3 ${className}`}>
      <p className="text-sm font-medium">{message}</p>
      <button className="text-sm font-semibold underline-offset-2 hover:underline" type="button" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}

function Card({ icon: Icon, label, value }: { icon: typeof Cpu; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <Icon className="h-5 w-5 text-zinc-500" aria-hidden="true" />
      <div className="mt-3 text-sm text-zinc-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-zinc-950">{value}</div>
    </div>
  );
}
