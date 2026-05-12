import type { ProxmoxNode } from '../types/proxmox';
import { formatBytes, formatPercent, formatUptime } from '../utils/format';
import { StatusBadge } from './StatusBadge';

type NodeCardsProps = {
  nodes: ProxmoxNode[];
};

export function NodeCards({ nodes }: NodeCardsProps) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">Cluster nodes</h3>
        <p className="mt-1 text-sm text-zinc-500">Read-only node state reported by Proxmox.</p>
      </div>
      <div className="grid gap-4 p-4 lg:grid-cols-2 xl:grid-cols-3">
        {nodes.map((node) => (
          <article key={node.name} className="rounded-lg border border-zinc-200 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="font-semibold text-zinc-950">{node.name}</h4>
                <p className="mt-1 text-sm text-zinc-500">{node.vm_count} VMs</p>
              </div>
              <StatusBadge status={node.status} />
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <Metric label="CPU" value={formatPercent(node.cpu_usage)} />
              <Metric label="Uptime" value={formatUptime(node.uptime_seconds)} />
              <Metric
                label="Memory"
                value={`${formatBytes(node.memory_used)} / ${formatBytes(node.memory_total)}`}
                wide
              />
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

function Metric({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? 'col-span-2' : undefined}>
      <dt className="text-xs font-medium uppercase tracking-normal text-zinc-500">{label}</dt>
      <dd className="mt-1 font-medium text-zinc-800">{value}</dd>
    </div>
  );
}
