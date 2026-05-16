import { useState } from 'react';
import { Copy, Expand } from 'lucide-react';

import type { Job } from '../types/job';
import { formatDateTime } from '../utils/format';

export function JobResultViewer({ job }: { job: Job | null }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!job) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Execution result</h3>
        <p className="mt-2 text-sm text-zinc-500">Select a job to inspect command output.</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">Execution result</h3>
            <p className="mt-1 text-sm text-zinc-500">
              Started {formatDateTime(job.started_at)} · Completed {formatDateTime(job.completed_at)} · Duration {formatDuration(job)}
            </p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={() => setIsExpanded(true)}
          >
            <Expand className="h-4 w-4" aria-hidden="true" />
            Expand
          </button>
        </div>
        <p className="mt-1 break-all font-mono text-sm text-zinc-500">{job.command}</p>
      </div>

      <div className="grid gap-4 p-5 lg:grid-cols-2">
        <OutputBlock label="stdout" value={job.stdout} />
        <OutputBlock label="stderr" value={job.stderr} tone="danger" />
      </div>
      {isExpanded ? <ExpandedModal job={job} onClose={() => setIsExpanded(false)} /> : null}
    </section>
  );
}

function OutputBlock({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: string | null;
  tone?: 'default' | 'danger';
}) {
  const className =
    tone === 'danger'
      ? 'border-rose-100 bg-rose-950 text-rose-50'
      : 'border-zinc-800 bg-zinc-950 text-zinc-50';

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="text-xs font-semibold uppercase tracking-normal text-zinc-500">{label}</div>
        <button
          className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2 py-1 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          type="button"
          onClick={() => void navigator.clipboard.writeText(value ?? '')}
        >
          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          Copy
        </button>
      </div>
      <pre className={`max-h-96 min-h-56 overflow-auto whitespace-pre-wrap rounded-md border p-3 text-xs leading-5 ${className}`}>
        {value?.trim() ? value : '(empty)'}
      </pre>
    </div>
  );
}

function ExpandedModal({ job, onClose }: { job: Job; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-zinc-950/70 p-4">
      <div className="mx-auto flex h-full max-w-6xl flex-col rounded-lg bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">{job.operation_type}</h3>
            <p className="mt-1 break-all font-mono text-sm text-zinc-500">{job.command}</p>
            <p className="mt-2 text-sm text-zinc-500">Duration {formatDuration(job)} · Exit {job.exit_code ?? '-'}</p>
          </div>
          <button className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-5 lg:grid-cols-2">
          <OutputBlock label="stdout" value={job.stdout} />
          <OutputBlock label="stderr" value={job.stderr} tone="danger" />
        </div>
      </div>
    </div>
  );
}

function formatDuration(job: Job): string {
  if (!job.started_at || !job.completed_at) {
    return 'Unavailable';
  }
  const seconds = Math.max(0, Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000));
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}
