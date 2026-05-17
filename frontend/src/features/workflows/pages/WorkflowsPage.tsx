import { useEffect, useMemo, useState } from 'react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listWorkflows } from '../api/workflowsApi';
import type { WorkflowRun, WorkflowStatus } from '../types/workflow';

const statusStyles: Record<WorkflowStatus, string> = {
  pending: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  queued: 'bg-sky-100 text-sky-700 ring-sky-200',
  running: 'bg-amber-100 text-amber-700 ring-amber-200',
  success: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
  failed: 'bg-rose-100 text-rose-700 ring-rose-200',
  cancelled: 'bg-orange-100 text-orange-700 ring-orange-200',
};

export function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedId) ?? workflows[0] ?? null,
    [selectedId, workflows],
  );

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const nextWorkflows = await listWorkflows();
      setWorkflows(nextWorkflows);
      setSelectedId((current) => current || nextWorkflows[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader title="Workflows" description="Persistent orchestration runs, timelines, logs, and background execution state." />
      {error ? <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">Workflow runs</h3>
            <p className="mt-1 text-sm text-zinc-500">{workflows.length} runs tracked.</p>
          </div>
          <button className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
        {isLoading ? <div className="m-5 h-28 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-50 text-left text-xs font-semibold uppercase text-zinc-500">
                <tr>
                  <th className="px-5 py-3">Type</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Trigger</th>
                  <th className="px-5 py-3">Duration</th>
                  <th className="px-5 py-3">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {workflows.map((workflow) => (
                  <tr key={workflow.id} className="cursor-pointer hover:bg-zinc-50" onClick={() => setSelectedId(workflow.id)}>
                    <td className="px-5 py-3 font-medium text-zinc-950">{formatLabel(workflow.workflow_type)}</td>
                    <td className="px-5 py-3"><WorkflowBadge status={workflow.status} /></td>
                    <td className="px-5 py-3 text-zinc-600">{formatLabel(workflow.trigger_source)}</td>
                    <td className="px-5 py-3 text-zinc-600">{duration(workflow.started_at, workflow.finished_at)}</td>
                    <td className="px-5 py-3 text-zinc-600">{formatDate(workflow.started_at ?? workflow.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {workflows.length === 0 ? <p className="p-5 text-sm text-zinc-500">No workflows have run yet.</p> : null}
          </div>
        ) : null}
      </section>

      <WorkflowDetail workflow={selectedWorkflow} />
    </div>
  );
}

function WorkflowDetail({ workflow }: { workflow: WorkflowRun | null }) {
  if (!workflow) {
    return null;
  }
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-base font-semibold text-zinc-950">{formatLabel(workflow.workflow_type)}</h3>
          <WorkflowBadge status={workflow.status} />
        </div>
        {workflow.error_message ? <p className="mt-2 text-sm text-rose-700">{workflow.error_message}</p> : null}
      </div>
      <ol className="divide-y divide-zinc-100">
        {workflow.steps.map((step) => (
          <li key={step.id} className="p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-zinc-950">{step.step_order}. {step.name}</p>
                <p className="mt-1 text-xs text-zinc-500">{formatLabel(step.step_type)} - {duration(step.started_at, step.finished_at)}</p>
              </div>
              <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-700">{step.status}</span>
            </div>
            <pre className="mt-3 max-h-44 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
              {step.log_output || step.error_output || '(no logs)'}
            </pre>
          </li>
        ))}
        {workflow.steps.length === 0 ? <li className="p-5 text-sm text-zinc-500">No steps have been persisted for this workflow yet.</li> : null}
      </ol>
    </section>
  );
}

function WorkflowBadge({ status }: { status: WorkflowStatus }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${statusStyles[status]}`}>
      {status}
    </span>
  );
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Not started';
}

function duration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt) return 'Not started';
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(startedAt).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
