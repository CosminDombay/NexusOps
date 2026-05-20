import { ChevronDown } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

type Tone = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'muted';

const toneClasses: Record<Tone, string> = {
  default: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  warning: 'bg-amber-50 text-amber-700 ring-amber-200',
  danger: 'bg-rose-50 text-rose-700 ring-rose-200',
  info: 'bg-sky-50 text-sky-700 ring-sky-200',
  muted: 'bg-zinc-100 text-zinc-600 ring-zinc-200',
};

export function RuntimeBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const tone: Tone =
    normalized.includes('success') || normalized === 'running' || normalized === 'online' || normalized === 'healthy'
      ? 'success'
      : normalized.includes('fail') || normalized.includes('unreachable') || normalized.includes('error')
        ? 'danger'
        : normalized.includes('degraded') || normalized.includes('partial') || normalized.includes('queued') || normalized.includes('deploying')
          ? 'warning'
          : normalized.includes('disabled') || normalized.includes('draft') || normalized.includes('stopped') || normalized.includes('cancelled')
            ? 'muted'
            : 'info';
  return <StatusPill tone={tone}>{formatOperationalLabel(value)}</StatusPill>;
}

export function StatusPill({ children, tone = 'default' }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${toneClasses[tone]}`}>
      {children}
    </span>
  );
}

export function PageActionButton({
  children,
  icon: Icon,
  onClick,
  tone = 'primary',
  disabled = false,
}: {
  children: ReactNode;
  icon?: LucideIcon;
  onClick: () => void;
  tone?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
}) {
  const className =
    tone === 'primary'
      ? 'border-zinc-900 bg-zinc-900 text-white hover:bg-zinc-800 disabled:border-zinc-300 disabled:bg-zinc-300'
      : tone === 'danger'
        ? 'border-rose-300 bg-white text-rose-700 hover:bg-rose-50 disabled:opacity-50'
        : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 disabled:opacity-50';
  return (
    <button
      className={`inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm font-semibold shadow-sm transition ${className}`}
      disabled={disabled}
      type="button"
      onClick={onClick}
    >
      {Icon ? <Icon className="h-4 w-4" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function OperationalToolbar({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 p-2">
      {children}
    </div>
  );
}

export function CollapsibleSection({
  title,
  description,
  children,
  defaultOpen = false,
  actions,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  actions?: ReactNode;
}) {
  return (
    <details className="rounded-lg border border-zinc-200 bg-white shadow-sm" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 marker:hidden">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
          {description ? <p className="mt-1 text-sm text-zinc-500">{description}</p> : null}
        </div>
        <div className="flex items-center gap-3">
          {actions}
          <ChevronDown className="h-4 w-4 text-zinc-500" aria-hidden="true" />
        </div>
      </summary>
      <div className="border-t border-zinc-200 p-5">{children}</div>
    </details>
  );
}

function formatOperationalLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
