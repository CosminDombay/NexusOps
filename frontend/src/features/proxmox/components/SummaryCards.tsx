import { Cpu, HardDrive, Server, Workflow } from 'lucide-react';

import type { ProxmoxClusterSummary } from '../types/proxmox';
import { formatBytes, formatPercent } from '../utils/format';

type SummaryCardsProps = {
  summary: ProxmoxClusterSummary;
};

export function SummaryCards({ summary }: SummaryCardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <SummaryCard icon={Server} label="Nodes online" value={`${summary.online_node_count}/${summary.node_count}`} />
      <SummaryCard icon={Workflow} label="VMs running" value={`${summary.running_vm_count}/${summary.vm_count}`} />
      <SummaryCard icon={Cpu} label="Cluster CPU" value={formatPercent(summary.cpu_usage)} />
      <SummaryCard
        icon={HardDrive}
        label="Cluster memory"
        value={`${formatBytes(summary.memory_used)} / ${formatBytes(summary.memory_total)}`}
      />
    </div>
  );
}

type SummaryCardProps = {
  icon: typeof Server;
  label: string;
  value: string;
};

function SummaryCard({ icon: Icon, label, value }: SummaryCardProps) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-zinc-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-zinc-950">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-zinc-950 text-white">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
