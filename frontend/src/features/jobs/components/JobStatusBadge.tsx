import type { JobStatus } from '../types/job';
import { jobStatusLabel } from '../utils/format';

const statusClassName: Record<JobStatus, string> = {
  pending: 'border-zinc-200 bg-zinc-50 text-zinc-700',
  queued: 'border-zinc-200 bg-zinc-50 text-zinc-700',
  dispatched: 'border-cyan-200 bg-cyan-50 text-cyan-700',
  running: 'border-sky-200 bg-sky-50 text-sky-700',
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  failed: 'border-rose-200 bg-rose-50 text-rose-700',
  cancelled: 'border-amber-200 bg-amber-50 text-amber-700',
  stale: 'border-orange-200 bg-orange-50 text-orange-700',
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusClassName[status]}`}>
      {jobStatusLabel(status)}
    </span>
  );
}
