import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

export type IdentityState = 'synced' | 'modified' | 'unmanaged' | 'pending' | 'failed' | 'discovered';

const stateStyles: Record<IdentityState, string> = {
  synced: 'bg-emerald-400/15 text-emerald-200 ring-emerald-300/30',
  modified: 'bg-amber-400/15 text-amber-200 ring-amber-300/30',
  unmanaged: 'bg-slate-400/15 text-slate-200 ring-slate-300/30',
  pending: 'bg-cyan-400/15 text-cyan-200 ring-cyan-300/30',
  failed: 'bg-rose-400/15 text-rose-200 ring-rose-300/30',
  discovered: 'bg-violet-400/15 text-violet-200 ring-violet-300/30',
};

export function StatusBadge({ state, label }: { state: IdentityState; label?: string }) {
  return (
    <span className={`inline-flex h-6 items-center rounded-full px-2 text-xs font-semibold capitalize ring-1 ${stateStyles[state]}`}>
      {label ?? state.replace('-', ' ')}
    </span>
  );
}

export function PermissionChip({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'privileged' | 'runtime' | 'observe' }) {
  const styles = {
    neutral: 'border-slate-600 bg-slate-900 text-slate-200',
    privileged: 'border-rose-400/40 bg-rose-500/10 text-rose-100',
    runtime: 'border-cyan-400/40 bg-cyan-500/10 text-cyan-100',
    observe: 'border-amber-400/40 bg-amber-500/10 text-amber-100',
  };
  return <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${styles[tone]}`}>{label}</span>;
}

export function MetricTile({ label, value, detail }: { label: string; value: ReactNode; detail?: string }) {
  return (
    <div className="rounded-md border border-slate-700 bg-slate-950/40 px-3 py-2">
      <p className="text-xs font-semibold uppercase text-slate-400">{label}</p>
      <div className="mt-1 text-lg font-semibold text-white">{value}</div>
      {detail ? <p className="mt-1 break-words text-xs text-slate-400">{detail}</p> : null}
    </div>
  );
}

export function SectionCard({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-md border border-slate-700 bg-slate-900/70 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export function IconButton({
  icon: Icon,
  label,
  disabled,
  onClick,
  variant = 'primary',
}: {
  icon: LucideIcon;
  label: string;
  disabled?: boolean;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
}) {
  const styles = {
    primary: 'border-cyan-300/60 bg-cyan-400 text-slate-950 hover:bg-cyan-300',
    secondary: 'border-slate-600 bg-slate-900 text-slate-100 hover:bg-slate-800',
    danger: 'border-rose-300/70 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20',
  };
  return (
    <button
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500 ${styles[variant]}`}
      disabled={disabled}
      type="button"
      onClick={onClick}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
    </button>
  );
}

export function TextInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase text-slate-400">{label}</span>
      <input
        className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function SelectInput({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase text-slate-400">{label}</span>
      <select
        className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none transition focus:border-cyan-300"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </select>
    </label>
  );
}
