import { AlertTriangle, ClipboardCopy, Download, Terminal, Wrench } from 'lucide-react';

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
  runtime_duration_seconds?: number | null;
  correlation_id?: string | null;
  runtime_metadata?: Record<string, unknown>;
  output_events?: Array<Record<string, unknown>>;
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
        <FailureCard key={job.id} job={job} />
      ))}
    </div>
  );
}

function FailureCard({ job }: { job: JobFailureSummary }) {
  const diagnosis = diagnoseFailure(job);
  const technicalDetails = buildTechnicalDetails(job);

  async function copyDetails() {
    if (!navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(technicalDetails);
  }

  function downloadDetails() {
    const blob = new Blob([technicalDetails], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `nexusops-job-${job.id}.log`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <article className="rounded-md border border-rose-200 bg-rose-50 p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="truncate font-mono text-xs font-semibold text-rose-950">
            {job.operation_type}
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5 text-[11px] font-semibold text-rose-700">
            {job.target_hostname ? <span>{job.target_hostname}</span> : null}
            {job.correlation_id ? <span>corr {job.correlation_id}</span> : null}
            {job.runtime_duration_seconds !== null && job.runtime_duration_seconds !== undefined ? (
              <span>{job.runtime_duration_seconds}s</span>
            ) : null}
          </div>
        </div>
        <span className="w-fit rounded-full bg-white px-2 py-1 text-xs font-semibold text-rose-700 ring-1 ring-inset ring-rose-200">
          {job.status}
          {job.exit_code === null || job.exit_code === undefined ? '' : ` - exit ${job.exit_code}`}
        </span>
      </div>

      <div className="mt-3 rounded-md border border-rose-200 bg-white p-3">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-rose-950">{diagnosis.summary}</p>
            <p className="mt-1 text-xs leading-5 text-rose-700">{diagnosis.reason}</p>
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase text-zinc-500">
              <Terminal className="h-3.5 w-3.5" aria-hidden="true" />
              Evidence
            </div>
            <pre className="mt-1 max-h-36 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
              {failureOutput(job)}
            </pre>
          </div>
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase text-zinc-500">
              <Wrench className="h-3.5 w-3.5" aria-hidden="true" />
              Suggested actions
            </div>
            <ul className="mt-1 space-y-1 text-xs leading-5 text-zinc-700">
              {diagnosis.actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <details className="mt-3 rounded-md border border-rose-200 bg-white">
        <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs font-semibold text-zinc-700 marker:hidden">
          Technical details
          <span className="flex gap-2">
            <button
              className="inline-flex items-center gap-1 rounded border border-zinc-200 px-2 py-1 text-[11px] text-zinc-600 hover:bg-zinc-50"
              type="button"
              onClick={(event) => {
                event.preventDefault();
                void copyDetails();
              }}
            >
              <ClipboardCopy className="h-3 w-3" aria-hidden="true" />
              Copy
            </button>
            <button
              className="inline-flex items-center gap-1 rounded border border-zinc-200 px-2 py-1 text-[11px] text-zinc-600 hover:bg-zinc-50"
              type="button"
              onClick={(event) => {
                event.preventDefault();
                downloadDetails();
              }}
            >
              <Download className="h-3 w-3" aria-hidden="true" />
              Download
            </button>
          </span>
        </summary>
        <div className="border-t border-rose-100 p-3">
          {job.command ? (
            <div>
              <p className="text-xs font-semibold uppercase text-zinc-500">Command</p>
              <pre className="mt-1 max-h-32 overflow-auto rounded bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
                {job.command}
              </pre>
            </div>
          ) : null}
          <pre className="mt-3 max-h-56 overflow-auto rounded bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
            {technicalDetails}
          </pre>
        </div>
      </details>
    </article>
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

type FailureDiagnosis = {
  summary: string;
  reason: string;
  actions: string[];
};

function diagnoseFailure(job: JobFailureSummary): FailureDiagnosis {
  const text = `${job.stderr ?? ''}\n${job.stdout ?? ''}\n${job.command ?? ''}`.toLowerCase();

  if (text.includes('permission denied') || text.includes('authentication failed')) {
    return {
      summary: 'Access to the target failed.',
      reason: 'The remote command reported an authentication or permission problem.',
      actions: [
        'Verify the selected execution or sudo credential.',
        'Confirm the SSH user can run the command manually.',
        'Check file ownership, sudoers, and group membership on the target.',
      ],
    };
  }

  if (text.includes('command denied by policy')) {
    return {
      summary: 'NexusOps blocked the command before execution.',
      reason: 'The command matched a protected operation and was not run on the target.',
      actions: [
        'Use a saved operational action for approved host-changing commands.',
        'Mark the action as Changes host when the operation is intentionally destructive.',
        'Keep raw profile scripts for non-destructive checks and setup commands.',
      ],
    };
  }

  if (text.includes('docker')) {
    return {
      summary: 'Docker validation or runtime execution failed.',
      reason: 'Docker was involved in the failed command. The daemon, socket access, image pull, or expected Docker root may not match the validation.',
      actions: [
        'Run docker info on the target and compare Docker Root Dir with the profile expectation.',
        'Confirm the SSH user has Docker socket access or use the sudo execution credential.',
        'Check whether the target can pull required images from the network.',
      ],
    };
  }

  if (text.includes('tailscale')) {
    return {
      summary: 'Tailscale setup or validation failed.',
      reason: 'The command reached Tailscale installation, authentication, or status validation and returned a non-zero exit.',
      actions: [
        'Confirm the auth key is valid and not expired.',
        'Run tailscale status --json on the target.',
        'Reset or edit the package if it still contains heredoc markers instead of terminal-style commands.',
      ],
    };
  }

  if (text.includes('no such file') || text.includes('not found')) {
    return {
      summary: 'A required command or path was missing.',
      reason: 'The target did not have an expected executable, file, directory, or mounted path.',
      actions: [
        'Check that prerequisite package/profile steps completed successfully.',
        'Verify the path or command exists on the target host.',
        'Review earlier steps in the execution sequence for the missing dependency.',
      ],
    };
  }

  return {
    summary: 'The remote operation returned a failure.',
    reason: job.exit_code === null || job.exit_code === undefined
      ? 'NexusOps marked the job failed, but no process exit code was captured.'
      : `The command exited with code ${job.exit_code}.`,
    actions: [
      'Review stderr/stdout below for the failing line.',
      'Run the same command manually on the target if the cause is unclear.',
      'Use the technical details panel when reporting or debugging this failure.',
    ],
  };
}

function buildTechnicalDetails(job: JobFailureSummary): string {
  return [
    `Job ID: ${job.id}`,
    `Operation: ${job.operation_type}`,
    `Status: ${job.status}`,
    `Exit code: ${job.exit_code ?? 'unknown'}`,
    `Target: ${job.target_hostname ?? 'unknown'}`,
    `Correlation ID: ${job.correlation_id ?? 'none'}`,
    `Duration seconds: ${job.runtime_duration_seconds ?? 'unknown'}`,
    '',
    'STDERR:',
    job.stderr?.trim() || '(empty)',
    '',
    'STDOUT:',
    job.stdout?.trim() || '(empty)',
    '',
    'Runtime metadata:',
    formatJson(job.runtime_metadata ?? {}),
    '',
    'Output events:',
    formatJson(job.output_events ?? []),
  ].join('\n');
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
