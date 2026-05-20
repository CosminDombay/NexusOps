import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertCircle, Cpu, HardDrive, Network, Power, RefreshCw, ServerIcon, ShieldCheck, Wrench } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { useAuth } from '../../auth/hooks/useAuth';
import { decommissionServer, deleteServer, restoreServer } from '../../inventory/api/serversApi';
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
      const confirmed = window.confirm(`${titleCase(action)} ${vm.type === 'lxc' ? 'LXC' : 'VM'} ${vm.name} (${vm.vm_id}) on ${vm.node}?`);
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

  async function handleHostLifecycle(action: 'disconnect' | 'reconnect' | 'remove') {
    const serverId = detail?.node.inventory_server_id;
    if (!serverId || !detail) {
      setNotification({ tone: 'error', message: 'Adopt this Proxmox host into Inventory before changing platform lifecycle.' });
      return;
    }

    const nodeName = detail.node.name;
    const prompts = {
      disconnect: `Disconnect Proxmox host ${nodeName} from active NexusOps orchestration? The physical host will not be powered off or modified.`,
      reconnect: `Reconnect Proxmox host ${nodeName} to active NexusOps orchestration?`,
      remove: `Remove the disconnected inventory record for ${nodeName}? Sync the Proxmox integration to rediscover it later.`,
    };
    if (!window.confirm(prompts[action])) {
      return;
    }

    setNotification(null);
    try {
      if (action === 'disconnect') {
        await decommissionServer(serverId);
        setNotification({ tone: 'success', message: `${nodeName} disconnected from active NexusOps orchestration.` });
      } else if (action === 'reconnect') {
        await restoreServer(serverId);
        setNotification({ tone: 'success', message: `${nodeName} reconnected to active NexusOps orchestration.` });
      } else {
        await deleteServer(serverId);
        setNotification({ tone: 'success', message: `${nodeName} inventory record removed. Integration sync can rediscover it.` });
      }
      await refresh();
    } catch (requestError) {
      setNotification({ tone: 'error', message: getApiErrorMessage(requestError) });
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
      <PageHeader title={node.name} description="Proxmox hypervisor host resources, managed inventory linkage, and hosted guests." />
      {notification ? <Notification message={notification.message} tone={notification.tone} onDismiss={() => setNotification(null)} /> : null}
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={node.status} />
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-200">
            Hypervisor host
          </span>
          {node.inventory_server_id ? (
            <Link className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200" to={`/inventory/${node.inventory_server_id}`}>
              Managed inventory: {node.inventory_hostname}
            </Link>
          ) : (
            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-200">
              Not adopted into inventory
            </span>
          )}
        </div>
        <button className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={() => void refresh()}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card icon={Cpu} label="CPU" value={formatPercent(node.cpu_usage)} />
        <Card icon={HardDrive} label="Memory" value={`${formatBytes(node.memory_used)} / ${formatBytes(node.memory_total)}`} />
        <Card icon={HardDrive} label="Storage" value={`${formatBytes(node.storage_used)} / ${formatBytes(node.storage_total)}`} />
        <Card icon={ServerIcon} label="VMs / LXCs" value={`${node.running_vm_count}/${node.vm_count} VMs, ${node.running_lxc_count}/${node.lxc_count} LXCs`} />
        <Card icon={Power} label="Uptime" value={formatUptime(node.uptime_seconds)} />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Panel title="Management" icon={ShieldCheck}>
          <Info label="Management IP" value={node.management_ip ?? 'Not discovered'} />
          <Info label="Inventory state" value={node.inventory_lifecycle_state ?? node.inventory_sync_status} />
          <Info label="Provider" value="Proxmox hypervisor node" />
          {allowActions && node.inventory_server_id ? (
            <div className="flex flex-wrap gap-2 pt-2">
              {isDisconnected(node) ? (
                <button
                  className="rounded-md border border-emerald-300 bg-white px-3 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-50"
                  type="button"
                  onClick={() => void handleHostLifecycle('reconnect')}
                >
                  Reconnect
                </button>
              ) : (
                <button
                  className="rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-50"
                  type="button"
                  onClick={() => void handleHostLifecycle('disconnect')}
                >
                  Disconnect
                </button>
              )}
              {isDisconnected(node) ? (
                <button
                  className="rounded-md border border-rose-300 bg-white px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50"
                  type="button"
                  onClick={() => void handleHostLifecycle('remove')}
                >
                  Remove record
                </button>
              ) : null}
            </div>
          ) : null}
        </Panel>
        <Panel title="Capabilities" icon={Wrench}>
          <div className="flex flex-wrap gap-2">
            {node.capabilities.map((capability) => (
              <span key={capability} className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-700 ring-1 ring-inset ring-zinc-200">
                {titleCase(capability.replace(/_/g, ' '))}
              </span>
            ))}
          </div>
        </Panel>
        <Panel title="Network Foundation" icon={Network}>
          <Info label="Interfaces" value={String(detail.network_interfaces.length)} />
          <Info label="Services" value={detail.detected_services.join(', ') || 'Not detected'} />
          <Info label="Filesystem" value={node.inventory_server_id ? 'Available through host tools' : 'Adopt host first'} />
        </Panel>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Hosted Guests</h3>
          <p className="mt-1 text-sm text-zinc-500">{vms.length} QEMU VM and LXC guest records reported by Proxmox. Hypervisor host controls are managed separately.</p>
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

function Panel({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Cpu;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950">
        <Icon className="h-4 w-4 text-zinc-500" aria-hidden="true" />
        {title}
      </div>
      <div className="mt-4 space-y-3">{children}</div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <span className="text-zinc-500">{label}</span>
      <span className="text-right font-medium text-zinc-800">{value}</span>
    </div>
  );
}

function isDisconnected(node: { inventory_lifecycle_state: string | null }): boolean {
  return node.inventory_lifecycle_state === 'archived' || node.inventory_lifecycle_state === 'decommissioned';
}
