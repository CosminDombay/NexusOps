import { useEffect, useMemo, useState } from 'react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { RuntimeBadge } from '../../../components/operations/OperationalComponents';
import { OperationalTimeline } from '../../../components/operations/OperationalTimeline';
import { formatDurationSeconds, formatOperationalLabel } from '../../../components/operations/runtimeFormat';
import { SearchField } from '../../../components/search/SearchField';
import { getApiErrorMessage } from '../../../lib/api/client';
import { matchesSearch } from '../../../lib/search/match';
import { listWorkflows } from '../api/workflowsApi';
import type { WorkflowRun, WorkflowStatus } from '../types/workflow';

export function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowRun[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');

  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedId) ?? workflows[0] ?? null,
    [selectedId, workflows],
  );
  const filteredWorkflows = useMemo(
    () =>
      workflows.filter((workflow) =>
        matchesSearch(search, [
          workflow.workflow_type,
          workflow.status,
          workflow.trigger_source,
          workflow.current_step,
          workflow.error_message,
          workflow.target_hostname,
          workflow.target_nodes,
          workflow.linked_job_ids,
          workflow.steps,
          workflow.activity_timeline,
        ]),
      ),
    [search, workflows],
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
        <div className="border-b border-zinc-200 px-5 py-4">
          <SearchField
            placeholder="Search workflows, hosts, steps, jobs..."
            value={search}
            onChange={setSearch}
          />
        </div>
        {isLoading ? <div className="m-5 h-28 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-50 text-left text-xs font-semibold uppercase text-zinc-500">
                <tr>
                  <th className="px-5 py-3">Type</th>
                  <th className="px-5 py-3">Target</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Progress</th>
                  <th className="px-5 py-3">Trigger</th>
                  <th className="px-5 py-3">Jobs</th>
                  <th className="px-5 py-3">Duration</th>
                  <th className="px-5 py-3">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filteredWorkflows.map((workflow) => (
                  <tr key={workflow.id} className="cursor-pointer hover:bg-zinc-50" onClick={() => setSelectedId(workflow.id)}>
                    <td className="px-5 py-3 font-medium text-zinc-950">{formatLabel(workflow.workflow_type)}</td>
                    <td className="px-5 py-3 text-zinc-600">{workflowTargetLabel(workflow)}</td>
                    <td className="px-5 py-3"><WorkflowBadge status={workflow.status} /></td>
                    <td className="px-5 py-3 text-zinc-600">{workflowProgress(workflow)}</td>
                    <td className="px-5 py-3 text-zinc-600">{formatLabel(workflow.trigger_source)}</td>
                    <td className="px-5 py-3 text-zinc-600">{workflow.linked_job_ids.length}</td>
                    <td className="px-5 py-3 text-zinc-600">{durationSeconds(workflow.duration_seconds, workflow.started_at, workflow.finished_at)}</td>
                    <td className="px-5 py-3 text-zinc-600">{formatDate(workflow.started_at ?? workflow.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredWorkflows.length === 0 ? (
              <p className="p-5 text-sm text-zinc-500">
                {search ? 'No workflows match this search.' : 'No workflows have run yet.'}
              </p>
            ) : null}
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
  const failedSteps = workflow.steps.filter((step) => step.status === 'failed');
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-base font-semibold text-zinc-950">{formatLabel(workflow.workflow_type)}</h3>
          <WorkflowBadge status={workflow.status} />
        </div>
        <div className="mt-3 grid gap-3 text-sm text-zinc-600 md:grid-cols-4">
          <RuntimeInfo label="Target" value={workflowTargetLabel(workflow)} />
          <RuntimeInfo label="Progress" value={workflowProgress(workflow)} />
          <RuntimeInfo label="Current step" value={workflow.current_step ?? 'None'} />
          <RuntimeInfo label="Linked jobs" value={workflow.linked_job_ids.length ? workflow.linked_job_ids.join(', ') : 'None'} />
        </div>
        {workflow.error_message ? <p className="mt-2 text-sm text-rose-700">{workflow.error_message}</p> : null}
        {failedSteps.length ? <WorkflowFailureDetails steps={failedSteps} /> : null}
      </div>
      <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_26rem]">
        <ol className="divide-y divide-zinc-100 rounded-md border border-zinc-200">
          {workflow.steps.map((step) => (
            <li key={step.id} className={`p-4 ${step.status === 'failed' ? 'bg-rose-50/70' : ''}`}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-zinc-950">{step.step_order}. {stepTitle(step)}</p>
                  <p className="mt-1 text-xs text-zinc-500">{formatLabel(step.step_type)} - {durationSeconds(null, step.started_at, step.finished_at)}</p>
                </div>
                <RuntimeBadge value={step.status} />
              </div>
              <pre className="mt-3 max-h-44 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
                {stepOutput(step)}
              </pre>
            </li>
          ))}
          {workflow.steps.length === 0 ? <li className="p-4 text-sm text-zinc-500">No steps have been persisted for this workflow yet.</li> : null}
        </ol>
        <div>
          <h4 className="mb-3 text-sm font-semibold text-zinc-950">Operational timeline</h4>
          <OperationalTimeline activities={workflow.activity_timeline} />
        </div>
      </div>
    </section>
  );
}

function WorkflowFailureDetails({ steps }: { steps: WorkflowRun['steps'] }) {
  return (
    <div className="mt-3 space-y-2 rounded-md border border-rose-200 bg-rose-50 p-3">
      <p className="text-sm font-semibold text-rose-700">Failed workflow step output</p>
      {steps.map((step) => (
        <div key={step.id} className="rounded-md border border-rose-200 bg-white p-3">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
            <p className="text-sm font-semibold text-rose-950">{step.step_order}. {stepTitle(step)}</p>
            <span className="w-fit rounded-full bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700 ring-1 ring-inset ring-rose-200">
              {step.status}
            </span>
          </div>
          <pre className="mt-2 max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
            {stepOutput(step)}
          </pre>
        </div>
      ))}
    </div>
  );
}

function WorkflowBadge({ status }: { status: WorkflowStatus }) {
  return <RuntimeBadge value={status} />;
}

function RuntimeInfo({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2">
      <div className="text-xs font-semibold uppercase text-zinc-500">{label}</div>
      <div className="mt-1 break-words font-semibold text-zinc-900">{value}</div>
    </div>
  );
}

function formatLabel(value: string): string {
  return formatOperationalLabel(value);
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Not started';
}

function workflowTargetLabel(workflow: WorkflowRun): string {
  if (workflow.target_nodes.length) {
    return workflow.target_nodes.join(', ');
  }
  if (workflow.target_hostname) {
    return workflow.target_hostname;
  }
  const stepHosts = Array.from(new Set(workflow.steps.map((step) => step.target_hostname).filter(Boolean)));
  if (stepHosts.length === 1) {
    return stepHosts[0] ?? 'Unknown target';
  }
  if (stepHosts.length > 1) {
    return `${stepHosts.length} hosts`;
  }
  return workflow.target_server_id ?? 'Multiple/unknown';
}

function workflowProgress(workflow: WorkflowRun): string {
  const total = workflow.steps.length;
  if (!total) {
    return 'No steps';
  }
  const failed = workflow.failed_steps ? `, ${workflow.failed_steps} failed` : '';
  return `${workflow.completed_steps}/${total} completed${failed}`;
}

function stepTitle(step: WorkflowRun['steps'][number]): string {
  if (!step.target_hostname) {
    return step.name;
  }
  const targetId = typeof step.metadata_json.target_server_id === 'string' ? step.metadata_json.target_server_id : '';
  return targetId ? step.name.replace(targetId, step.target_hostname) : `${step.name} on ${step.target_hostname}`;
}

function stepOutput(step: WorkflowRun['steps'][number]): string {
  if (step.status === 'failed') {
    return step.error_output?.trim() || step.log_output?.trim() || '(no logs)';
  }
  return step.log_output?.trim() || step.error_output?.trim() || '(no logs)';
}

function durationSeconds(value: number | null, startedAt: string | null, finishedAt: string | null): string {
  if (value != null) {
    return formatDurationSeconds(value);
  }
  if (!startedAt) return 'Not started';
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(startedAt).getTime()) / 1000));
  return formatDurationSeconds(seconds);
}
