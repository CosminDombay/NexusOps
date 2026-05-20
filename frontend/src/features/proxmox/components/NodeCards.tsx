import { Link } from 'react-router-dom';

import type { ProxmoxNode } from '../types/proxmox';
import { formatBytes, formatPercent, formatUptime } from '../utils/format';
import { StatusBadge } from './StatusBadge';

type NodeCardsProps = {
  nodes: ProxmoxNode[];
  allowManagement?: boolean;
  onDecommission?: (serverId: string, nodeName: string) => void;
  onReconnect?: (serverId: string, nodeName: string) => void;
  onRemoveRecord?: (serverId: string, nodeName: string) => void;
};

export function NodeCards({ nodes, allowManagement = false, onDecommission, onReconnect, onRemoveRecord }: NodeCardsProps) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">Proxmox hypervisor hosts</h3>
        <p className="mt-1 text-sm text-zinc-500">Physical Proxmox nodes are separate from guest VMs and future LXC containers.</p>
      </div>
      <div className="grid gap-4 p-4 lg:grid-cols-2 xl:grid-cols-3">
        {nodes.map((node) => (
          <article key={node.name} className="rounded-lg border border-zinc-200 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <Link className="font-semibold text-zinc-950 hover:text-zinc-700" to={`/infrastructure/nodes/${node.name}`}>
                  {node.name}
                </Link>
                {node.inventory_server_id ? (
                  <Link className="mt-1 block text-xs font-semibold text-zinc-600 hover:text-zinc-950" to={`/nodes/${node.inventory_server_id}`}>
                    Open operations
                  </Link>
                ) : null}
                <p className="mt-1 text-sm text-zinc-500">
                  {node.running_vm_count}/{node.vm_count} VMs, {node.running_lxc_count}/{node.lxc_count} LXCs
                </p>
                <p className="mt-1 font-mono text-xs text-zinc-500">{node.management_ip ?? 'IP not discovered'}</p>
              </div>
              <StatusBadge status={node.status} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-200">Hypervisor</span>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${inventoryTone(node)}`}>
                {inventoryLabel(node)}
              </span>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <Metric label="CPU" value={formatPercent(node.cpu_usage)} />
              <Metric label="Uptime" value={formatUptime(node.uptime_seconds)} />
              <Metric
                label="Memory"
                value={`${formatBytes(node.memory_used)} / ${formatBytes(node.memory_total)}`}
                wide
              />
              <Metric
                label="Storage"
                value={`${formatBytes(node.storage_used)} / ${formatBytes(node.storage_total)}`}
                wide
              />
            </dl>
            {allowManagement && node.inventory_server_id ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {isDisconnected(node) ? (
                  <button
                    className="rounded-md border border-emerald-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-50"
                    type="button"
                    onClick={() => onReconnect?.(node.inventory_server_id!, node.name)}
                  >
                    Reconnect
                  </button>
                ) : (
                  <button
                    className="rounded-md border border-amber-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-50"
                    type="button"
                    onClick={() => onDecommission?.(node.inventory_server_id!, node.name)}
                  >
                    Disconnect
                  </button>
                )}
                {isDisconnected(node) ? (
                  <button
                    className="rounded-md border border-rose-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50"
                    type="button"
                    onClick={() => onRemoveRecord?.(node.inventory_server_id!, node.name)}
                  >
                    Remove record
                  </button>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function isDisconnected(node: ProxmoxNode): boolean {
  return node.inventory_lifecycle_state === 'archived' || node.inventory_lifecycle_state === 'decommissioned';
}

function inventoryLabel(node: ProxmoxNode): string {
  if (!node.inventory_server_id) return 'Not adopted';
  if (isDisconnected(node)) return 'Disconnected';
  if (node.inventory_sync_status === 'unmanaged') return 'Unmanaged';
  return 'Managed inventory';
}

function inventoryTone(node: ProxmoxNode): string {
  if (!node.inventory_server_id) return 'bg-amber-50 text-amber-700 ring-amber-200';
  if (isDisconnected(node)) return 'bg-stone-100 text-stone-700 ring-stone-200';
  if (node.inventory_sync_status === 'unmanaged') return 'bg-amber-50 text-amber-700 ring-amber-200';
  return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
}

function Metric({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? 'col-span-2' : undefined}>
      <dt className="text-xs font-medium uppercase tracking-normal text-zinc-500">{label}</dt>
      <dd className="mt-1 font-medium text-zinc-800">{value}</dd>
    </div>
  );
}
