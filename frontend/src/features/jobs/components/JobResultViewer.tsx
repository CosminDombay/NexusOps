import type { Job } from '../types/job';

export function JobResultViewer({ job }: { job: Job | null }) {
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
        <h3 className="text-base font-semibold text-zinc-950">Execution result</h3>
        <p className="mt-1 break-all font-mono text-sm text-zinc-500">{job.command}</p>
      </div>

      <div className="grid gap-4 p-5 lg:grid-cols-2">
        <OutputBlock label="stdout" value={job.stdout} />
        <OutputBlock label="stderr" value={job.stderr} tone="danger" />
      </div>
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
      <div className="mb-2 text-xs font-semibold uppercase tracking-normal text-zinc-500">{label}</div>
      <pre className={`min-h-36 overflow-auto rounded-md border p-3 text-xs leading-5 ${className}`}>
        {value?.trim() ? value : '(empty)'}
      </pre>
    </div>
  );
}
