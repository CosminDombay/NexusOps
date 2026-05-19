import { Download, Loader2, Play, Power, RotateCw } from 'lucide-react';

import type { ProxmoxVm, ProxmoxVmAction } from '../types/proxmox';
import { formatBytes, formatPercent, titleCase } from '../utils/format';
import { StatusBadge } from './StatusBadge';

type VmTableProps = {
  vms: ProxmoxVm[];
  actionByVmId: Record<number, ProxmoxVmAction | undefined>;
  allowActions: boolean;
  allowImport?: boolean;
  onAction: (vm: ProxmoxVm, action: ProxmoxVmAction) => void;
  onImport: (vm: ProxmoxVm) => void;
};

export function VmTable({ vms, actionByVmId, allowActions, allowImport = allowActions, onAction, onImport }: VmTableProps) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">Virtual machines</h3>
        <p className="mt-1 text-sm text-zinc-500">{vms.length} guests discovered from Proxmox.</p>
      </div>

      <div className="hidden overflow-x-auto lg:block">
        <table className="min-w-full divide-y divide-zinc-200">
          <thead className="bg-zinc-50">
            <tr>
              {['VM', 'Node', 'Type', 'Status', 'Inventory', 'CPU', 'Memory', 'Actions'].map(
                (heading) => (
                  <th
                    key={heading}
                    className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-normal text-zinc-500"
                  >
                  {heading}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {vms.map((vm) => (
              <tr key={`${vm.node}-${vm.type}-${vm.vm_id}`} className="hover:bg-zinc-50">
                <td className="px-5 py-4">
                  <div className="font-medium text-zinc-950">{vm.name}</div>
                  <div className="mt-1 text-xs text-zinc-500">VMID {vm.vm_id}</div>
                </td>
                <td className="px-5 py-4 text-sm text-zinc-700">{vm.node}</td>
                <td className="px-5 py-4 text-sm text-zinc-700">{titleCase(vm.type)}</td>
                <td className="px-5 py-4">
                  <StatusBadge status={vm.status} />
                </td>
                <td className="px-5 py-4">
                  <InventoryBadge status={vm.inventory_sync_status} />
                  {vm.inventory_hostname ? (
                    <div className="mt-1 text-xs text-zinc-500">
                      {vm.inventory_hostname}
                      {vm.inventory_lifecycle_state ? ` - ${titleCase(vm.inventory_lifecycle_state)}` : ''}
                    </div>
                  ) : null}
                </td>
                <td className="px-5 py-4 text-sm text-zinc-700">{formatPercent(vm.cpu_usage)}</td>
                <td className="px-5 py-4 text-sm text-zinc-700">
                  {formatBytes(vm.memory_used)} / {formatBytes(vm.memory_total)}
                </td>
                <td className="px-5 py-4">
                  <VmActions
                    activeAction={actionByVmId[vm.vm_id]}
                    vm={vm}
                    allowActions={allowActions}
                    allowImport={allowImport}
                    onAction={onAction}
                    onImport={onImport}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 p-4 lg:hidden">
        {vms.map((vm) => (
          <article key={`${vm.node}-${vm.type}-${vm.vm_id}`} className="rounded-lg border border-zinc-200 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="font-semibold text-zinc-950">{vm.name}</h4>
                <p className="mt-1 text-sm text-zinc-500">
                  VMID {vm.vm_id} on {vm.node}
                </p>
              </div>
              <StatusBadge status={vm.status} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <InventoryBadge status={vm.inventory_sync_status} />
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <Metric label="Type" value={titleCase(vm.type)} />
              <Metric label="CPU" value={formatPercent(vm.cpu_usage)} />
              <Metric
                label="Memory"
                value={`${formatBytes(vm.memory_used)} / ${formatBytes(vm.memory_total)}`}
                wide
              />
            </dl>
            <div className="mt-4">
              <VmActions
                activeAction={actionByVmId[vm.vm_id]}
                vm={vm}
                allowActions={allowActions}
                allowImport={allowImport}
                onAction={onAction}
                onImport={onImport}
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function VmActions({
  vm,
  activeAction,
  allowActions,
  allowImport,
  onAction,
  onImport,
}: {
  vm: ProxmoxVm;
  activeAction: ProxmoxVmAction | undefined;
  allowActions: boolean;
  allowImport: boolean;
  onAction: (vm: ProxmoxVm, action: ProxmoxVmAction) => void;
  onImport: (vm: ProxmoxVm) => void;
}) {
  const isRunning = vm.status === 'running';
  const isBusy = Boolean(activeAction);
  const canImport = vm.inventory_sync_status === 'unmanaged' || vm.inventory_sync_status === 'archived';

  if (!allowActions) {
    return (
      <div className="flex flex-wrap gap-2">
        <span className="text-xs font-medium text-zinc-500">Lifecycle actions live in Inventory</span>
        {allowImport ? (
          <button
            className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-50 disabled:cursor-not-allowed disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400"
            disabled={!canImport}
            type="button"
            onClick={() => onImport(vm)}
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" />
            {vm.inventory_sync_status === 'archived' ? 'Re-import' : 'Import'}
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      <ActionButton
        action="start"
        disabled={isRunning || isBusy}
        icon={Play}
        isLoading={activeAction === 'start'}
        label="Start"
        tone="primary"
        onClick={() => onAction(vm, 'start')}
      />
      <ActionButton
        action="shutdown"
        disabled={!isRunning || isBusy}
        icon={Power}
        isLoading={activeAction === 'shutdown'}
        label="Shutdown"
        onClick={() => onAction(vm, 'shutdown')}
      />
      <ActionButton
        action="reboot"
        disabled={!isRunning || isBusy}
        icon={RotateCw}
        isLoading={activeAction === 'reboot'}
        label="Reboot"
        onClick={() => onAction(vm, 'reboot')}
      />
      <ActionButton
        action="stop"
        disabled={!isRunning || isBusy}
        icon={Power}
        isLoading={activeAction === 'stop'}
        label="Stop"
        tone="danger"
        onClick={() => onAction(vm, 'stop')}
      />
      {allowImport ? (
        <button
          className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-50 disabled:cursor-not-allowed disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400"
          disabled={!canImport}
          type="button"
          onClick={() => onImport(vm)}
        >
          <Download className="h-3.5 w-3.5" aria-hidden="true" />
          {vm.inventory_sync_status === 'archived' ? 'Re-import' : 'Import'}
        </button>
      ) : null}
    </div>
  );
}

function ActionButton({
  disabled,
  icon: Icon,
  isLoading,
  label,
  onClick,
  tone = 'secondary',
}: {
  action: ProxmoxVmAction;
  disabled: boolean;
  icon: typeof Play;
  isLoading: boolean;
  label: string;
  onClick: () => void;
  tone?: 'primary' | 'secondary' | 'danger';
}) {
  const className =
    tone === 'primary'
      ? 'border-zinc-900 bg-zinc-950 text-white hover:bg-zinc-800 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
      : tone === 'danger'
      ? 'border-rose-300 bg-white text-rose-700 hover:bg-rose-50 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
      : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 disabled:bg-zinc-100 disabled:text-zinc-400';

  return (
    <button
      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-semibold transition disabled:cursor-not-allowed ${className}`}
      disabled={disabled}
      type="button"
      onClick={onClick}
    >
      {isLoading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
      ) : (
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      {label}
    </button>
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

function InventoryBadge({ status }: { status: ProxmoxVm['inventory_sync_status'] }) {
  const className =
    status === 'synced'
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : status === 'mismatch'
        ? 'bg-orange-50 text-orange-700 ring-orange-200'
        : status === 'orphaned'
          ? 'bg-rose-50 text-rose-700 ring-rose-200'
          : 'bg-amber-50 text-amber-700 ring-amber-200';

  const label =
    status === 'synced'
      ? 'Managed in Inventory'
      : status === 'archived'
        ? 'Inactive in Inventory'
        : status === 'unmanaged'
          ? 'Discovered Only'
          : titleCase(status);

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${className}`}>
      {label}
    </span>
  );
}
