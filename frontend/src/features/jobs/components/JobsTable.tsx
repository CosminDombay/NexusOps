import { RefreshCw } from 'lucide-react';

import type { Job } from '../types/job';
import { formatDateTime } from '../utils/format';
import { JobStatusBadge } from './JobStatusBadge';

type JobsTableProps = {
  error: string | null;
  isLoading: boolean;
  jobs: Job[];
  selectedJobId: string | null;
  onRefresh: () => void;
  onSelectJob: (job: Job) => void;
};

export function JobsTable({
  error,
  isLoading,
  jobs,
  selectedJobId,
  onRefresh,
  onSelectJob,
}: JobsTableProps) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-zinc-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">Job history</h3>
          <p className="mt-1 text-sm text-zinc-500">{jobs.length} executions persisted.</p>
        </div>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={onRefresh}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>

      {error ? <p className="m-5 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
      {isLoading ? <LoadingRows /> : null}
      {!isLoading && !error && jobs.length === 0 ? (
        <p className="p-5 text-sm text-zinc-500">No jobs have been executed yet.</p>
      ) : null}

      {!isLoading && jobs.length > 0 ? (
        <>
          <div className="hidden overflow-x-auto lg:block">
            <table className="min-w-full divide-y divide-zinc-200">
              <thead className="bg-zinc-50">
                <tr>
                  {['Target', 'Operation', 'Command', 'Status', 'Exit', 'Completed'].map((heading) => (
                    <th
                      key={heading}
                      className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-normal text-zinc-500"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className={`cursor-pointer hover:bg-zinc-50 ${
                      selectedJobId === job.id ? 'bg-zinc-50' : ''
                    }`}
                    onClick={() => onSelectJob(job)}
                  >
                    <td className="px-5 py-4 text-sm font-medium text-zinc-950">
                      {job.target_hostname ?? 'Unknown host'}
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-700">{job.operation_type}</td>
                    <td className="max-w-md truncate px-5 py-4 font-mono text-sm text-zinc-700">
                      {job.command}
                    </td>
                    <td className="px-5 py-4">
                      <JobStatusBadge status={job.status} />
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-700">
                      {job.exit_code ?? '-'}
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-700">
                      {formatDateTime(job.completed_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid gap-3 p-4 lg:hidden">
            {jobs.map((job) => (
              <button
                key={job.id}
                className={`rounded-lg border p-4 text-left ${
                  selectedJobId === job.id ? 'border-zinc-950' : 'border-zinc-200'
                }`}
                type="button"
                onClick={() => onSelectJob(job)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="font-semibold text-zinc-950">
                      {job.target_hostname ?? 'Unknown host'}
                    </h4>
                    <p className="mt-1 text-sm text-zinc-500">{job.operation_type}</p>
                  </div>
                  <JobStatusBadge status={job.status} />
                </div>
                <p className="mt-3 break-all font-mono text-sm text-zinc-800">{job.command}</p>
                <p className="mt-3 text-xs text-zinc-500">{formatDateTime(job.completed_at)}</p>
              </button>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}

function LoadingRows() {
  return (
    <div className="space-y-3 p-5">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-14 animate-pulse rounded-md bg-zinc-100" />
      ))}
    </div>
  );
}
