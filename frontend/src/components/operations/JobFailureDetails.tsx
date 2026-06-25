import { isFailedJobStatus } from './jobStatus';

export type JobFailureSummary = {
  id: string;
  operation_type: string;
  status: string;
  command?: string | null;
  stdout?: string | null;
  stderr?: string | null;
  exit_code?: number | null;
  target_hostname?: string | null;
};

type JobFailureDetailsProps = {
  jobs: JobFailureSummary[];
  emptyMessage?: string;
  title?: string;
};

export function JobFailureDetails({
  jobs,
  emptyMessage = 'No failed jobs recorded.',
  title = 'Failed job output',
}: JobFailureDetailsProps) {
  const failedJobs = jobs.filter((job) => isFailedJobStatus(job.status));

  if (failedJobs.length === 0) {
    return <p className="text-xs text-zinc-500">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-rose-700">{title}</p>
      {failedJobs.map((job) => (
        <article key={job.id} className="rounded-md border border-rose-200 bg-rose-50 p-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="truncate font-mono text-xs font-semibold text-rose-950">
                {job.operation_type}
              </p>
              {job.target_hostname ? (
                <p className="mt-1 text-xs text-rose-700">{job.target_hostname}</p>
              ) : null}
            </div>
            <span className="w-fit rounded-full bg-white px-2 py-1 text-xs font-semibold text-rose-700 ring-1 ring-inset ring-rose-200">
              {job.status}
              {job.exit_code === null || job.exit_code === undefined ? '' : ` · exit ${job.exit_code}`}
            </span>
          </div>
          {job.command ? (
            <p className="mt-2 break-all font-mono text-xs text-rose-700">{job.command}</p>
          ) : null}
          <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
            {failureOutput(job)}
          </pre>
        </article>
      ))}
    </div>
  );
}

function failureOutput(job: JobFailureSummary): string {
  const stderr = job.stderr?.trim();
  if (stderr) {
    return stderr;
  }
  const stdout = job.stdout?.trim();
  if (stdout) {
    return stdout;
  }
  return '(no stderr/stdout captured)';
}
