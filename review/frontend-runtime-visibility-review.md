# Frontend Runtime Visibility Review

Generated from the current NexusOps workspace for focused code review.

## frontend/src/components/operations/OperationalComponents.tsx

``tsx
import { ChevronDown } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

import { formatOperationalLabel } from './runtimeFormat';

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

````

## frontend/src/components/operations/OperationalTimeline.tsx

``tsx
import { RuntimeBadge } from './OperationalComponents';
import { formatDateTime } from './runtimeFormat';
import type { OperationalActivity } from './runtimeTypes';

const markerClassName: Record<string, string> = {
  info: 'border-sky-200 bg-sky-50',
  success: 'border-emerald-200 bg-emerald-50',
  warning: 'border-amber-200 bg-amber-50',
  danger: 'border-rose-200 bg-rose-50',
};

export function OperationalTimeline({
  activities,
  emptyText = 'No runtime activity has been recorded yet.',
}: {
  activities: OperationalActivity[];
  emptyText?: string;
}) {
  if (!activities.length) {
    return <p className="text-sm text-zinc-500">{emptyText}</p>;
  }

  return (
    <ol className="space-y-3">
      {activities.map((activity) => (
        <li key={activity.id} className="grid grid-cols-[auto_1fr] gap-3">
          <span
            className={`mt-1 h-3 w-3 rounded-full border ${markerClassName[activity.severity] ?? markerClassName.info}`}
            aria-hidden="true"
          />
          <div className="rounded-md border border-zinc-200 bg-white px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-zinc-950">{activity.title}</p>
                <p className="text-xs text-zinc-500">{formatDateTime(activity.occurred_at)}</p>
              </div>
              {activity.status ? <RuntimeBadge value={activity.status} /> : null}
            </div>
            {activity.message ? (
              <p className="mt-2 whitespace-pre-wrap break-words text-xs text-zinc-600">{activity.message}</p>
            ) : null}
            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-semibold text-zinc-500">
              <span className="rounded-full bg-zinc-100 px-2 py-1">{activity.event_type}</span>
              {activity.correlation_id ? <span className="rounded-full bg-zinc-100 px-2 py-1">corr {activity.correlation_id}</span> : null}
              {activity.job_ids.map((jobId) => (
                <span key={jobId} className="rounded-full bg-zinc-100 px-2 py-1">job {jobId}</span>
              ))}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

````

## frontend/src/components/operations/runtimeFormat.ts

``typescript
export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return 'Not started';
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function formatDurationSeconds(value: number | null | undefined): string {
  if (value == null) {
    return 'Unavailable';
  }
  if (value < 60) {
    return `${value}s`;
  }
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

export function formatOperationalLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

````

## frontend/src/components/operations/runtimeTypes.ts

``typescript
export type OperationalActivity = {
  id: string;
  source_type: string;
  source_id: string;
  event_type: string;
  title: string;
  status: string | null;
  severity: 'info' | 'success' | 'warning' | 'danger' | string;
  occurred_at: string | null;
  message: string | null;
  correlation_id: string | null;
  job_ids: string[];
  metadata: Record<string, unknown>;
};

````

## frontend/src/features/jobs/api/jobsApi.ts

``typescript
import { apiClient } from '../../../lib/api/client';
import type {
  BulkExecutionResponse,
  CreateOperationalActionPayload,
  ExecuteActionPayload,
  ExecuteJobBulkPayload,
  ExecuteJobPayload,
  Job,
  OperationalAction,
  UpdateOperationalActionPayload,
} from '../types/job';

export async function listJobs(filters: { targetServerId?: string } = {}): Promise<Job[]> {
  const response = await apiClient.get<Job[]>('/jobs', {
    params: filters.targetServerId ? { target_server_id: filters.targetServerId } : undefined,
  });
  return response.data;
}

export async function executeJob(payload: ExecuteJobPayload): Promise<Job> {
  const response = await apiClient.post<Job>('/jobs/execute', payload);
  return response.data;
}

export async function executeJobBulk(payload: ExecuteJobBulkPayload): Promise<BulkExecutionResponse> {
  const response = await apiClient.post<BulkExecutionResponse>('/jobs/execute/bulk', payload);
  return response.data;
}

export async function listOperationalActions(): Promise<OperationalAction[]> {
  const response = await apiClient.get<OperationalAction[]>('/jobs/actions');
  return response.data;
}

export async function executeOperationalAction(payload: ExecuteActionPayload): Promise<Job> {
  const response = await apiClient.post<Job>('/jobs/actions/execute', payload);
  return response.data;
}

export async function createOperationalAction(payload: CreateOperationalActionPayload): Promise<OperationalAction> {
  const response = await apiClient.post<OperationalAction>('/jobs/actions', payload);
  return response.data;
}

export async function updateOperationalAction(actionId: string, payload: UpdateOperationalActionPayload): Promise<OperationalAction> {
  const response = await apiClient.put<OperationalAction>(`/jobs/actions/${actionId}`, payload);
  return response.data;
}

export async function deleteOperationalAction(actionId: string): Promise<void> {
  await apiClient.delete(`/jobs/actions/${actionId}`);
}

````

## frontend/src/features/jobs/types/job.ts

``typescript
import type { OperationalActivity } from '../../../components/operations/runtimeTypes';

export type JobStatus = 'pending' | 'queued' | 'dispatched' | 'running' | 'completed' | 'success' | 'failed' | 'cancelled' | 'stale';

export type Job = {
  id: string;
  target_server_id: string;
  target_hostname: string | null;
  operation_type: string;
  command: string;
  status: JobStatus;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  queued_at: string | null;
  dispatched_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  runtime_duration_seconds: number | null;
  execution_origin: string;
  correlation_id: string | null;
  cancellation_requested_at: string | null;
  runtime_metadata: Record<string, unknown>;
  output_events: Array<Record<string, unknown>>;
  activity_timeline: OperationalActivity[];
  created_at: string;
  updated_at: string;
};

export type ExecuteJobPayload = {
  target_server_id: string;
  command: string;
  operation_type: string;
  credential_ref?: string | null;
  max_parallel?: number;
};

export type BulkExecutionResult = {
  target_server_id: string;
  target_hostname: string | null;
  success: boolean;
  job: Job | null;
  error: string | null;
};

export type BulkExecutionResponse = {
  operation_type: string;
  success_count: number;
  failure_count: number;
  results: BulkExecutionResult[];
};

export type ExecuteJobBulkPayload = {
  target_server_ids: string[];
  command: string;
  operation_type: string;
  credential_ref?: string | null;
};

export type OperationalAction = {
  id: string;
  name: string;
  category: string;
  description: string;
  command: string;
  destructive: boolean;
  is_builtin: boolean;
};

export type ExecuteActionPayload = {
  target_server_id: string;
  action_id: string;
  credential_ref?: string | null;
};

export type CreateOperationalActionPayload = {
  id: string;
  name: string;
  category: string;
  description: string;
  command: string;
  destructive: boolean;
};

export type UpdateOperationalActionPayload = Omit<CreateOperationalActionPayload, 'id'>;

````

## frontend/src/features/jobs/components/JobResultViewer.tsx

``tsx
import { useState } from 'react';
import { Copy, Expand, WrapText } from 'lucide-react';

import { OperationalTimeline } from '../../../components/operations/OperationalTimeline';
import { formatDurationSeconds } from '../../../components/operations/runtimeFormat';
import type { Job } from '../types/job';
import { formatDateTime } from '../utils/format';

type OutputTab = 'stdout' | 'stderr' | 'command' | 'metadata';

export function JobResultViewer({ job }: { job: Job | null }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<OutputTab>('stdout');
  const [wrapOutput, setWrapOutput] = useState(true);

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
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-zinc-950">Execution result</h3>
            <p className="mt-1 text-sm text-zinc-500">
              Started {formatDateTime(job.started_at)} Â· Completed {formatDateTime(job.completed_at)} Â· Duration {formatDuration(job)}
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
        <p className="mt-2 truncate font-mono text-sm text-zinc-500">{job.command}</p>
      </div>

      <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <OutputInspector
          activeTab={activeTab}
          job={job}
          wrapOutput={wrapOutput}
          onTabChange={setActiveTab}
          onToggleWrap={() => setWrapOutput((current) => !current)}
        />
        <div>
          <h4 className="mb-3 text-sm font-semibold text-zinc-950">Runtime timeline</h4>
          <OperationalTimeline activities={job.activity_timeline} />
        </div>
      </div>
      {isExpanded ? (
        <ExpandedModal
          activeTab={activeTab}
          job={job}
          wrapOutput={wrapOutput}
          onClose={() => setIsExpanded(false)}
          onTabChange={setActiveTab}
          onToggleWrap={() => setWrapOutput((current) => !current)}
        />
      ) : null}
    </section>
  );
}

function OutputInspector({
  activeTab,
  job,
  wrapOutput,
  onTabChange,
  onToggleWrap,
}: {
  activeTab: OutputTab;
  job: Job;
  wrapOutput: boolean;
  onTabChange: (tab: OutputTab) => void;
  onToggleWrap: () => void;
}) {
  const value = getTabValue(job, activeTab);

  return (
    <div className="flex h-full min-h-0 flex-col rounded-lg border border-zinc-200 bg-white">
      <div className="flex flex-col gap-3 border-b border-zinc-200 p-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap gap-2">
          {(['stdout', 'stderr', 'command', 'metadata'] as OutputTab[]).map((tab) => (
            <button
              key={tab}
              className={[
                'rounded-md px-3 py-1.5 text-sm font-semibold capitalize transition',
                activeTab === tab ? 'bg-zinc-950 text-white' : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200',
              ].join(' ')}
              type="button"
              onClick={() => onTabChange(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button
            className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2.5 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={onToggleWrap}
          >
            <WrapText className="h-3.5 w-3.5" aria-hidden="true" />
            {wrapOutput ? 'Wrap on' : 'Wrap off'}
          </button>
          <button
            className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2.5 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={() => void navigator.clipboard.writeText(value)}
          >
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
            Copy
          </button>
        </div>
      </div>
      <pre
        className={[
          'max-h-[34rem] min-h-80 flex-1 overflow-auto rounded-b-lg bg-zinc-950 p-4 text-xs leading-5 text-zinc-50',
          wrapOutput ? 'whitespace-pre-wrap break-words' : 'whitespace-pre',
        ].join(' ')}
      >
        {value.trim() || '(empty)'}
      </pre>
    </div>
  );
}

function ExpandedModal({
  activeTab,
  job,
  wrapOutput,
  onClose,
  onTabChange,
  onToggleWrap,
}: {
  activeTab: OutputTab;
  job: Job;
  wrapOutput: boolean;
  onClose: () => void;
  onTabChange: (tab: OutputTab) => void;
  onToggleWrap: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-zinc-950/70 p-4">
      <div className="mx-auto flex h-full max-w-7xl flex-col rounded-lg bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-zinc-950">{job.operation_type}</h3>
            <p className="mt-1 truncate font-mono text-sm text-zinc-500">{job.command}</p>
            <p className="mt-2 text-sm text-zinc-500">Duration {formatDuration(job)} Â· Exit {job.exit_code ?? '-'}</p>
          </div>
          <button className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden p-5">
          <OutputInspector
            activeTab={activeTab}
            job={job}
            wrapOutput={wrapOutput}
            onTabChange={onTabChange}
            onToggleWrap={onToggleWrap}
          />
        </div>
      </div>
    </div>
  );
}

function getTabValue(job: Job, tab: OutputTab): string {
  if (tab === 'stdout') {
    return job.stdout ?? '';
  }
  if (tab === 'stderr') {
    return job.stderr ?? '';
  }
  if (tab === 'command') {
    return job.command;
  }
  return [
    `Target: ${job.target_hostname ?? job.target_server_id}`,
    `Operation: ${job.operation_type}`,
    `Status: ${job.status}`,
    `Exit code: ${job.exit_code ?? '-'}`,
    `Started: ${formatDateTime(job.started_at)}`,
    `Completed: ${formatDateTime(job.completed_at)}`,
    `Duration: ${formatDuration(job)}`,
  ].join('\n');
}

function formatDuration(job: Job): string {
  if (job.runtime_duration_seconds != null) {
    return formatDurationSeconds(job.runtime_duration_seconds);
  }
  if (!job.started_at || !job.completed_at) return 'Unavailable';
  const seconds = Math.max(0, Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000));
  return formatDurationSeconds(seconds);
}

````

## frontend/src/features/jobs/components/JobsTable.tsx

``tsx
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
                  {['Target', 'Operation', 'Command', 'Status', 'Exit', 'Duration', 'Completed'].map((heading) => (
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
                      {formatDuration(job.started_at, job.completed_at)}
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

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) {
    return '-';
  }
  const seconds = Math.max(0, Math.round((new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
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

````

## frontend/src/features/jobs/JobsPage.tsx

``tsx
import { useCallback, useEffect, useMemo, useState } from 'react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { CollapsibleSection, PageActionButton } from '../../components/operations/OperationalComponents';
import { getApiErrorMessage } from '../../lib/api/client';
import { listServers } from '../inventory/api/serversApi';
import type { Server } from '../inventory/types/server';
import {
  createOperationalAction,
  deleteOperationalAction,
  executeJob,
  executeJobBulk,
  executeOperationalAction,
  listJobs,
  listOperationalActions,
  updateOperationalAction,
} from './api/jobsApi';
import { JobResultViewer } from './components/JobResultViewer';
import { JobsTable } from './components/JobsTable';
import { OperationalActionsPanel } from './components/OperationalActionsPanel';
import { RunCommandPanel } from './components/RunCommandPanel';
import type { CreateOperationalActionPayload, Job, OperationalAction } from './types/job';

type ActionFormState = CreateOperationalActionPayload;

const initialActionForm: ActionFormState = {
  id: '',
  name: '',
  category: 'Custom',
  description: '',
  command: '',
  destructive: false,
};

export function JobsPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [selectedActionId, setSelectedActionId] = useState('');
  const [operationType, setOperationType] = useState('command');
  const [command, setCommand] = useState('uptime');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isExecutingAction, setIsExecutingAction] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [executeError, setExecuteError] = useState<string | null>(null);
  const [bulkResult, setBulkResult] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionForm, setActionForm] = useState<ActionFormState>(initialActionForm);
  const [editingActionId, setEditingActionId] = useState<string | null>(null);
  const [isSavingAction, setIsSavingAction] = useState(false);
  const [isActionBuilderOpen, setIsActionBuilderOpen] = useState(false);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null,
    [jobs, selectedJobId],
  );

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const [nextServers, nextJobs, nextActions] = await Promise.all([
        listServers(),
        listJobs(),
        listOperationalActions(),
      ]);
      setServers(nextServers);
      setJobs(nextJobs);
      setActions(nextActions);
      setSelectedServerId((current) => current || nextServers[0]?.id || '');
      setSelectedActionId((current) => current || nextActions[0]?.id || '');
    } catch (error) {
      setLoadError(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  async function handleExecute() {
    if ((!selectedServerId && selectedServerIds.length === 0) || !command.trim()) {
      return;
    }

    setIsExecuting(true);
    setExecuteError(null);

    try {
      if (selectedServerIds.length > 0) {
        const result = await executeJobBulk({
          target_server_ids: selectedServerIds,
          operation_type: operationType,
          command,
        });
        const resultJobs = result.results.flatMap((item) => (item.job ? [item.job] : []));
        setJobs((currentJobs) => [...resultJobs, ...currentJobs]);
        setSelectedJobId(resultJobs[0]?.id ?? null);
        setBulkResult(`${result.success_count} succeeded, ${result.failure_count} failed`);
      } else {
        const job = await executeJob({
          target_server_id: selectedServerId,
          operation_type: operationType,
          command,
        });
        setJobs((currentJobs) => [job, ...currentJobs]);
        setSelectedJobId(job.id);
        setBulkResult(null);
      }
    } catch (error) {
      setExecuteError(getApiErrorMessage(error));
    } finally {
      setIsExecuting(false);
    }
  }

  async function handleExecuteAction() {
    if (!selectedServerId || !selectedActionId) {
      return;
    }

    const action = actions.find((candidate) => candidate.id === selectedActionId);
    if (action?.destructive) {
      const confirmed = window.confirm(`Run ${action.name} on the selected host?`);
      if (!confirmed) {
        return;
      }
    }

    setIsExecutingAction(true);
    setActionError(null);

    try {
      const job = await executeOperationalAction({
        target_server_id: selectedServerId,
        action_id: selectedActionId,
      });
      setJobs((currentJobs) => [job, ...currentJobs]);
      setSelectedJobId(job.id);
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    } finally {
      setIsExecutingAction(false);
    }
  }

  function updateActionField<K extends keyof ActionFormState>(field: K, value: ActionFormState[K]) {
    setActionForm((current) => ({ ...current, [field]: value }));
    setActionError(null);
  }

  function startEditAction(action: OperationalAction) {
    if (action.is_builtin) {
      return;
    }
    setIsActionBuilderOpen(true);
    setEditingActionId(action.id);
    setActionForm({
      id: action.id,
      name: action.name,
      category: action.category,
      description: action.description,
      command: action.command,
      destructive: action.destructive,
    });
    setActionError(null);
  }

  function resetActionForm() {
    setEditingActionId(null);
    setActionForm(initialActionForm);
    setIsActionBuilderOpen(false);
  }

  async function saveAction() {
    if (!actionForm.id.trim() || !actionForm.name.trim() || !actionForm.command.trim()) {
      setActionError('Action id, name, and command are required.');
      return;
    }
    setIsSavingAction(true);
    setActionError(null);
    try {
      if (editingActionId) {
        const updated = await updateOperationalAction(editingActionId, {
          name: actionForm.name,
          category: actionForm.category,
          description: actionForm.description,
          command: actionForm.command,
          destructive: actionForm.destructive,
        });
        setActions((current) =>
          current.map((action) => (action.id === updated.id ? updated : action)),
        );
        setSelectedActionId(updated.id);
      } else {
        const created = await createOperationalAction(actionForm);
        setActions((current) => [...current, created]);
        setSelectedActionId(created.id);
      }
      resetActionForm();
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    } finally {
      setIsSavingAction(false);
    }
  }

  async function removeAction(action: OperationalAction) {
    if (action.is_builtin) {
      return;
    }
    const confirmed = window.confirm(`Delete custom action ${action.name}?`);
    if (!confirmed) {
      return;
    }
    setActionError(null);
    try {
      await deleteOperationalAction(action.id);
      const nextActions = actions.filter((candidate) => candidate.id !== action.id);
      setActions(nextActions);
      setSelectedActionId((current) =>
        current === action.id ? (nextActions[0]?.id ?? '') : current,
      );
      if (editingActionId === action.id) {
        resetActionForm();
      }
    } catch (error) {
      setActionError(getApiErrorMessage(error));
    }
  }

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Jobs"
        description="Reusable operational actions, remote command execution, and orchestration history."
        actions={
          <PageActionButton tone="secondary" onClick={() => setIsActionBuilderOpen(true)}>
            Create custom action
          </PageActionButton>
        }
      />

      <CollapsibleSection
        title="Operational action runner"
        description="Run a saved action against an inventory-managed node."
        defaultOpen
      >
        <OperationalActionsPanel
          actions={actions}
          error={actionError}
          isExecuting={isExecutingAction}
          selectedActionId={selectedActionId}
          selectedServerId={selectedServerId}
          servers={servers}
          onExecute={handleExecuteAction}
          onDeleteAction={removeAction}
          onEditAction={startEditAction}
          onSelectedActionChange={setSelectedActionId}
          onSelectedServerChange={setSelectedServerId}
        />
      </CollapsibleSection>

      <ContextDrawer
        description="Save reusable command sequences and scripts that execute through Jobs."
        isOpen={isActionBuilderOpen}
        title={editingActionId ? 'Edit Custom Action' : 'Create Custom Action'}
        width="xl"
        onClose={resetActionForm}
      >
        <CustomActionBuilder
          editingActionId={editingActionId}
          form={actionForm}
          isSaving={isSavingAction}
          onCancel={resetActionForm}
          onFieldChange={updateActionField}
          onSave={saveAction}
        />
      </ContextDrawer>

      <CollapsibleSection
        title="Raw command runner"
        description="Use for direct diagnostics and one-off commands. Saved actions should be preferred for repeatable operations."
      >
        <RunCommandPanel
          command={command}
          error={executeError}
          isExecuting={isExecuting}
          operationType={operationType}
          selectedServerId={selectedServerId}
          selectedServerIds={selectedServerIds}
          servers={servers}
          onCommandChange={setCommand}
          onOperationTypeChange={setOperationType}
          onSelectedServerChange={setSelectedServerId}
          onSelectedServersChange={setSelectedServerIds}
          onSubmit={handleExecute}
        />
      </CollapsibleSection>
      {bulkResult ? (
        <p className="rounded-md bg-zinc-100 px-3 py-2 text-sm text-zinc-700">{bulkResult}</p>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(480px,1fr)]">
        <JobsTable
          error={loadError}
          isLoading={isLoading}
          jobs={jobs}
          selectedJobId={selectedJob?.id ?? null}
          onRefresh={refresh}
          onSelectJob={(job) => setSelectedJobId(job.id)}
        />
        <JobResultViewer job={selectedJob} />
      </div>
    </div>
  );
}

function CustomActionBuilder({
  editingActionId,
  form,
  isSaving,
  onCancel,
  onFieldChange,
  onSave,
}: {
  editingActionId: string | null;
  form: ActionFormState;
  isSaving: boolean;
  onCancel: () => void;
  onFieldChange: <K extends keyof ActionFormState>(field: K, value: ActionFormState[K]) => void;
  onSave: () => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-950">
            {editingActionId ? 'Edit custom action' : 'Create custom action'}
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Save reusable command sequences and scripts that execute through Jobs.
          </p>
        </div>
        {editingActionId ? (
          <button
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={onCancel}
          >
            Cancel edit
          </button>
        ) : null}
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label className="block text-sm font-medium text-zinc-700">
          ID
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm disabled:bg-zinc-100"
            disabled={Boolean(editingActionId)}
            placeholder="enable-docker-user"
            value={form.id}
            onChange={(event) => onFieldChange('id', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700">
          Name
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.name}
            onChange={(event) => onFieldChange('name', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700">
          Category
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.category}
            onChange={(event) => onFieldChange('category', event.target.value)}
          />
        </label>
        <label className="flex items-end gap-2 pb-2 text-sm font-medium text-zinc-700">
          <input
            checked={form.destructive}
            type="checkbox"
            onChange={(event) => onFieldChange('destructive', event.target.checked)}
          />
          Changes host
        </label>
        <label className="block text-sm font-medium text-zinc-700 md:col-span-2 xl:col-span-4">
          Description
          <input
            className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
            value={form.description}
            onChange={(event) => onFieldChange('description', event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium text-zinc-700 md:col-span-2 xl:col-span-4">
          Command or script
          <textarea
            className="mt-1 min-h-36 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
            placeholder={'set -e\nsudo usermod -aG docker $USER\nid'}
            value={form.command}
            onChange={(event) => onFieldChange('command', event.target.value)}
          />
        </label>
      </div>
      <div className="mt-4 flex justify-end">
        <button
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-zinc-300"
          disabled={isSaving}
          type="button"
          onClick={onSave}
        >
          {isSaving ? 'Saving' : editingActionId ? 'Save action' : 'Create action'}
        </button>
      </div>
    </section>
  );
}

````

## frontend/src/features/workflows/api/workflowsApi.ts

``typescript
import { apiClient } from '../../../lib/api/client';
import type { WorkflowRun } from '../types/workflow';

export async function listWorkflows(filters: { targetServerId?: string } = {}): Promise<WorkflowRun[]> {
  const response = await apiClient.get<WorkflowRun[]>('/workflows', {
    params: filters.targetServerId ? { target_server_id: filters.targetServerId } : undefined,
  });
  return response.data;
}

export async function getWorkflow(workflowId: string): Promise<WorkflowRun> {
  const response = await apiClient.get<WorkflowRun>(`/workflows/${workflowId}`);
  return response.data;
}

````

## frontend/src/features/workflows/types/workflow.ts

``typescript
import type { OperationalActivity } from '../../../components/operations/runtimeTypes';

export type WorkflowStatus = 'pending' | 'queued' | 'running' | 'success' | 'failed' | 'cancelled';

export type WorkflowStepStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

export type WorkflowStep = {
  id: string;
  workflow_run_id: string;
  step_order: number;
  step_type: string;
  name: string;
  status: WorkflowStepStatus;
  started_at: string | null;
  finished_at: string | null;
  log_output: string;
  error_output: string;
  metadata_json: Record<string, unknown>;
  target_hostname: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkflowRun = {
  id: string;
  workflow_type: string;
  status: WorkflowStatus;
  trigger_source: string;
  started_at: string | null;
  finished_at: string | null;
  target_server_id: string | null;
  target_hostname: string | null;
  initiated_by: string | null;
  context_json: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  steps: WorkflowStep[];
  current_step: string | null;
  completed_steps: number;
  failed_steps: number;
  duration_seconds: number | null;
  target_nodes: string[];
  linked_job_ids: string[];
  activity_timeline: OperationalActivity[];
  created_at: string;
  updated_at: string;
};

````

## frontend/src/features/workflows/pages/WorkflowsPage.tsx

``tsx
import { useEffect, useMemo, useState } from 'react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { RuntimeBadge } from '../../../components/operations/OperationalComponents';
import { OperationalTimeline } from '../../../components/operations/OperationalTimeline';
import { formatDurationSeconds, formatOperationalLabel } from '../../../components/operations/runtimeFormat';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listWorkflows } from '../api/workflowsApi';
import type { WorkflowRun, WorkflowStatus } from '../types/workflow';

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
                {workflows.map((workflow) => (
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
        <div className="mt-3 grid gap-3 text-sm text-zinc-600 md:grid-cols-4">
          <RuntimeInfo label="Target" value={workflowTargetLabel(workflow)} />
          <RuntimeInfo label="Progress" value={workflowProgress(workflow)} />
          <RuntimeInfo label="Current step" value={workflow.current_step ?? 'None'} />
          <RuntimeInfo label="Linked jobs" value={workflow.linked_job_ids.length ? workflow.linked_job_ids.join(', ') : 'None'} />
        </div>
        {workflow.error_message ? <p className="mt-2 text-sm text-rose-700">{workflow.error_message}</p> : null}
      </div>
      <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_26rem]">
        <ol className="divide-y divide-zinc-100 rounded-md border border-zinc-200">
          {workflow.steps.map((step) => (
            <li key={step.id} className="p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-zinc-950">{step.step_order}. {stepTitle(step)}</p>
                  <p className="mt-1 text-xs text-zinc-500">{formatLabel(step.step_type)} - {durationSeconds(null, step.started_at, step.finished_at)}</p>
                </div>
                <RuntimeBadge value={step.status} />
              </div>
              <pre className="mt-3 max-h-44 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
                {step.log_output || step.error_output || '(no logs)'}
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

function durationSeconds(value: number | null, startedAt: string | null, finishedAt: string | null): string {
  if (value != null) {
    return formatDurationSeconds(value);
  }
  if (!startedAt) return 'Not started';
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(startedAt).getTime()) / 1000));
  return formatDurationSeconds(seconds);
}

````

## frontend/src/features/automations/api/automationsApi.ts

``typescript
import { apiClient } from '../../../lib/api/client';
import type { Automation, AutomationPayload, AutomationRunResult } from '../types/automation';

export async function listAutomations(filters: { targetServerId?: string } = {}): Promise<Automation[]> {
  const response = await apiClient.get<Automation[]>('/automations', {
    params: filters.targetServerId ? { target_server_id: filters.targetServerId } : undefined,
  });
  return response.data;
}

export async function createAutomation(payload: AutomationPayload): Promise<Automation> {
  const response = await apiClient.post<Automation>('/automations', payload);
  return response.data;
}

export async function updateAutomation(automationId: string, payload: Partial<AutomationPayload>): Promise<Automation> {
  const response = await apiClient.put<Automation>(`/automations/${automationId}`, payload);
  return response.data;
}

export async function deleteAutomation(automationId: string): Promise<void> {
  await apiClient.delete(`/automations/${automationId}`);
}

export async function enableAutomation(automationId: string): Promise<Automation> {
  const response = await apiClient.post<Automation>(`/automations/${automationId}/enable`);
  return response.data;
}

export async function disableAutomation(automationId: string): Promise<Automation> {
  const response = await apiClient.post<Automation>(`/automations/${automationId}/disable`);
  return response.data;
}

export async function runAutomation(automationId: string): Promise<AutomationRunResult> {
  const response = await apiClient.post<AutomationRunResult>(`/automations/${automationId}/run`);
  return response.data;
}

````

## frontend/src/features/automations/types/automation.ts

``typescript
import type { WorkflowRun } from '../../workflows/types/workflow';

export type AutomationTarget = {
  id: string;
  hostname: string;
  node_type: string;
  environment: string;
  provider: string;
  source: string;
  tags: string[];
};

export type Automation = {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  schedule_type: 'interval' | 'cron';
  cron_expression: string | null;
  interval_seconds: number | null;
  target_mode: 'single_host' | 'multiple_hosts';
  target_server_ids: string[];
  operation_type: 'action' | 'profile' | 'package' | 'deployment' | 'command';
  reference_id: string | null;
  raw_command: string | null;
  variables_json: Record<string, string>;
  credential_refs: Record<string, string>;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  runtime_state: 'idle' | 'queued' | 'running' | 'success' | 'failed' | 'partial_success' | 'disabled' | 'cancelled';
  last_success_at: string | null;
  last_failure_at: string | null;
  last_duration_seconds: number | null;
  execution_count: number;
  target_nodes: AutomationTarget[];
  recent_executions: WorkflowRun[];
  created_at: string;
  updated_at: string;
};

export type AutomationPayload = {
  name: string;
  description?: string | null;
  enabled: boolean;
  schedule_type: 'interval' | 'cron';
  cron_expression?: string | null;
  interval_seconds?: number | null;
  target_mode: 'single_host' | 'multiple_hosts';
  target_server_ids: string[];
  operation_type: 'action' | 'profile' | 'package';
  reference_id: string;
  variables_json?: Record<string, string>;
  credential_refs?: Record<string, string>;
};

export type AutomationRunResult = WorkflowRun;

````

## frontend/src/features/automations/pages/AutomationsPage.tsx

``tsx
import { useEffect, useMemo, useState } from 'react';
import { Clock3, History, Pencil, Play, Plus, Trash2 } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { ContextDrawer } from '../../../components/ContextDrawer';
import { PageHeader } from '../../../components/layout/PageHeader';
import { PageActionButton, RuntimeBadge, OperationalToolbar } from '../../../components/operations/OperationalComponents';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listServers } from '../../inventory/api/serversApi';
import { TargetSelector } from '../../inventory/components/TargetSelector';
import { useTargetSelection } from '../../inventory/hooks/useTargetSelection';
import type { Server } from '../../inventory/types/server';
import { listOperationalActions } from '../../jobs/api/jobsApi';
import type { OperationalAction } from '../../jobs/types/job';
import { listPackageDefinitions } from '../../packages/api/packagesApi';
import type { PackageDefinition } from '../../packages/types/package';
import { listProfiles } from '../../profiles/api/profilesApi';
import type { InfrastructureProfile } from '../../profiles/types/profile';
import {
  createAutomation,
  deleteAutomation,
  disableAutomation,
  enableAutomation,
  listAutomations,
  runAutomation,
  updateAutomation,
} from '../api/automationsApi';
import type { Automation, AutomationPayload } from '../types/automation';

type FormState = {
  name: string;
  schedule_type: 'interval' | 'cron';
  interval_seconds: string;
  cron_expression: string;
  target_server_ids: string[];
  operation_type: 'action' | 'profile' | 'package';
  reference_id: string;
};

const initialForm: FormState = {
  name: 'Hourly uptime check',
  schedule_type: 'interval',
  interval_seconds: '3600',
  cron_expression: '0 2 * * *',
  target_server_ids: [],
  operation_type: 'action',
  reference_id: 'check-uptime',
};

export function AutomationsPage() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [form, setForm] = useState<FormState>(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [editingAutomationId, setEditingAutomationId] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const targetSelector = useTargetSelection('bulk');

  const operationOptions = useMemo(() => {
    if (form.operation_type === 'profile')
      return profiles.map((profile) => ({ value: profile.id, label: profile.name }));
    if (form.operation_type === 'package')
      return packages.map((pkg) => ({ value: pkg.id, label: pkg.name }));
    return actions.map((action) => ({ value: action.id, label: action.name }));
  }, [actions, form.operation_type, packages, profiles]);

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextAutomations, nextServers, nextActions, nextProfiles, nextPackages] =
        await Promise.all([
          listAutomations(),
          listServers(),
          listOperationalActions(),
          listProfiles(),
          listPackageDefinitions(),
        ]);
      setAutomations(nextAutomations);
      setServers(nextServers);
      setActions(nextActions);
      setProfiles(nextProfiles);
      setPackages(nextPackages);
      setForm((current) => ({
        ...current,
        target_server_ids: current.target_server_ids.length
          ? current.target_server_ids
          : nextServers[0]
            ? [nextServers[0].id]
            : [],
        reference_id: current.reference_id || nextActions[0]?.id || '',
      }));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSave() {
    const payload = toPayload(form);
    if (!payload) {
      setError('Automation needs a name, target host, schedule, and operation reference.');
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      if (editingAutomationId) {
        const updated = await updateAutomation(editingAutomationId, payload);
        setAutomations((current) =>
          current.map((automation) => (automation.id === updated.id ? updated : automation)),
        );
        setSuccess(`Updated automation ${updated.name}.`);
        resetForm();
      } else {
        const created = await createAutomation(payload);
        setAutomations((current) => [created, ...current]);
        setSuccess(`Created automation ${created.name}.`);
        setIsFormOpen(false);
      }
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  function startEdit(automation: Automation) {
    setIsFormOpen(true);
    setEditingAutomationId(automation.id);
    setForm({
      name: automation.name,
      schedule_type: automation.schedule_type,
      interval_seconds: String(automation.interval_seconds ?? 3600),
      cron_expression: automation.cron_expression ?? '0 2 * * *',
      target_server_ids: automation.target_server_ids,
      operation_type:
        automation.operation_type === 'profile' || automation.operation_type === 'package'
          ? automation.operation_type
          : 'action',
      reference_id: automation.reference_id ?? '',
    });
    targetSelector.setMode(automation.target_server_ids.length > 1 ? 'bulk' : 'single');
    targetSelector.setSelectedId(automation.target_server_ids[0] ?? '');
    targetSelector.setSelectedIds(automation.target_server_ids);
    setError(null);
    setSuccess(null);
  }

  function resetForm() {
    setEditingAutomationId(null);
    setIsFormOpen(false);
    setForm({
      ...initialForm,
      target_server_ids: servers[0] ? [servers[0].id] : [],
      reference_id: actions[0]?.id ?? '',
    });
    targetSelector.setMode('bulk');
    targetSelector.setSelectedId(servers[0]?.id ?? '');
    targetSelector.setSelectedIds(servers[0] ? [servers[0].id] : []);
  }

  async function handleDelete(automation: Automation) {
    const confirmed = window.confirm(
      `Delete automation ${automation.name}? Scheduled runs will stop, but existing workflow/job history remains.`,
    );
    if (!confirmed) {
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      await deleteAutomation(automation.id);
      setAutomations((current) => current.filter((item) => item.id !== automation.id));
      if (editingAutomationId === automation.id) {
        resetForm();
      }
      setSuccess(`Deleted automation ${automation.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function toggle(automation: Automation) {
    setIsWorking(true);
    try {
      const updated = automation.enabled
        ? await disableAutomation(automation.id)
        : await enableAutomation(automation.id);
      setAutomations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function runNow(automation: Automation) {
    setIsWorking(true);
    setError(null);
    try {
      const workflow = await runAutomation(automation.id);
      setSuccess(`Queued workflow ${workflow.id}.`);
      await refresh();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Automations"
        description="Recurring operational checks and package/profile compliance runs backed by persistent workflows."
        actions={
          <PageActionButton icon={Plus} onClick={() => setIsFormOpen(true)}>
            Create automation
          </PageActionButton>
        }
      />
      {error ? (
        <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>
      ) : null}
      {success ? (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p>
      ) : null}

      <ContextDrawer
        description="Schedule actions, packages, or profiles while preserving the automation list context."
        isOpen={isFormOpen}
        title={editingAutomationId ? 'Edit Automation' : 'Create Automation'}
        width="xl"
        onClose={resetForm}
      >
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <TextInput
            label="Name"
            value={form.name}
            onChange={(value) => setForm({ ...form, name: value })}
          />
          <label className="text-sm font-medium text-zinc-700">
            Schedule
            <select
              className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={form.schedule_type}
              onChange={(event) =>
                setForm({
                  ...form,
                  schedule_type: event.target.value as FormState['schedule_type'],
                })
              }
            >
              <option value="interval">Interval</option>
              <option value="cron">Cron</option>
            </select>
          </label>
          {form.schedule_type === 'interval' ? (
            <TextInput
              label="Every seconds"
              value={form.interval_seconds}
              onChange={(value) => setForm({ ...form, interval_seconds: value })}
            />
          ) : (
            <TextInput
              label="Cron expression"
              value={form.cron_expression}
              onChange={(value) => setForm({ ...form, cron_expression: value })}
            />
          )}
          <label className="text-sm font-medium text-zinc-700">
            Operation
            <select
              className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={form.operation_type}
              onChange={(event) => {
                const operationType = event.target.value as FormState['operation_type'];
                setForm({ ...form, operation_type: operationType, reference_id: '' });
              }}
            >
              <option value="action">Predefined action</option>
              <option value="package">Package</option>
              <option value="profile">Profile</option>
            </select>
          </label>
          <label className="text-sm font-medium text-zinc-700">
            Reference
            <select
              className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={form.reference_id}
              onChange={(event) => setForm({ ...form, reference_id: event.target.value })}
            >
              <option value="">Select operation</option>
              {operationOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div className="lg:col-span-3">
            <TargetSelector
              servers={servers}
              selection={{ ...targetSelector.selection, selectedIds: form.target_server_ids }}
              filters={targetSelector.filters}
              title="Automation targets"
              description="Schedule actions, packages, or profiles against consistent inventory host selections."
              onFiltersChange={targetSelector.setFilters}
              onSelectionChange={(selection) => {
                targetSelector.setMode(selection.mode);
                targetSelector.setSelectedId(selection.selectedId);
                targetSelector.setSelectedIds(selection.selectedIds);
                setForm({
                  ...form,
                  target_server_ids:
                    selection.mode === 'bulk'
                      ? selection.selectedIds
                      : selection.selectedId
                        ? [selection.selectedId]
                        : [],
                });
              }}
            />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <PageActionButton disabled={isWorking} onClick={() => void handleSave()}>
            {editingAutomationId ? 'Save automation' : 'Create automation'}
          </PageActionButton>
        </div>
      </ContextDrawer>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Scheduled automations</h3>
          <p className="mt-1 text-sm text-zinc-500">{automations.length} configured.</p>
        </div>
        {isLoading ? <div className="m-5 h-24 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <div className="divide-y divide-zinc-100">
            {automations.map((automation) => (
              <article key={automation.id} className="grid gap-4 p-5 xl:grid-cols-[minmax(0,1fr)_auto]">
                <div className="space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="font-semibold text-zinc-950">{automation.name}</h4>
                        <RuntimeBadge value={automation.runtime_state} />
                        <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">
                          {automation.enabled ? 'enabled' : 'disabled'}
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-zinc-500">
                        {automation.schedule_type === 'interval'
                          ? `Every ${automation.interval_seconds}s`
                          : automation.cron_expression}{' '}
                        - {automation.operation_type} {automation.reference_id}
                      </p>
                    </div>
                    <div className="grid gap-2 text-xs text-zinc-500 sm:grid-cols-3">
                      <RuntimeFact label="Last run" value={formatDate(automation.last_run_at)} />
                      <RuntimeFact label="Next run" value={formatDate(automation.next_run_at)} />
                      <RuntimeFact label="Executions" value={String(automation.execution_count)} />
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase text-zinc-500">Targets</p>
                    <AutomationTargets automation={automation} servers={servers} />
                  </div>

                  <div className="grid gap-3 lg:grid-cols-3">
                    <RuntimeMetric icon={Clock3} label="Last duration" value={formatDurationSeconds(automation.last_duration_seconds)} />
                    <RuntimeMetric icon={History} label="Last success" value={formatDate(automation.last_success_at)} />
                    <RuntimeMetric icon={History} label="Last failure" value={formatDate(automation.last_failure_at)} />
                  </div>

                  <RecentExecutions automation={automation} />
                </div>
                <OperationalToolbar>
                  <button
                    className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700"
                    disabled={isWorking}
                    type="button"
                    onClick={() => void toggle(automation)}
                  >
                    {automation.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700"
                    disabled={isWorking}
                    type="button"
                    onClick={() => startEdit(automation)}
                  >
                    <Pencil className="h-4 w-4" aria-hidden="true" />
                    Edit
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md bg-zinc-950 px-3 py-2 text-sm font-semibold text-white disabled:bg-zinc-300"
                    disabled={isWorking}
                    type="button"
                    onClick={() => void runNow(automation)}
                  >
                    <Play className="h-4 w-4" aria-hidden="true" />
                    Run now
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700"
                    disabled={isWorking}
                    type="button"
                    onClick={() => void handleDelete(automation)}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    Delete
                  </button>
                </OperationalToolbar>
              </article>
            ))}
            {automations.length === 0 ? (
              <p className="p-5 text-sm text-zinc-500">No scheduled automations yet.</p>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function TextInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input
        className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function AutomationTargets({ automation, servers }: { automation: Automation; servers: Server[] }) {
  const targets = automation.target_nodes.length
    ? automation.target_nodes
    : automation.target_server_ids.map((serverId) => {
        const server = servers.find((candidate) => candidate.id === serverId);
        return {
          id: serverId,
          hostname: server?.hostname ?? serverId,
          node_type: server?.node_type ?? 'unknown',
          environment: server?.environment ?? 'unknown',
          provider: server?.provider ?? 'unknown',
          source: server?.source ?? 'unknown',
          tags: server?.tags ?? [],
        };
      });

  if (!targets.length) {
    return <p className="text-sm text-zinc-500">No targets selected.</p>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {targets.map((target) => (
        <div key={target.id} className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-zinc-950">{target.hostname}</span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-zinc-700 ring-1 ring-inset ring-zinc-200">
              {formatNodeType(target.node_type)}
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            {target.environment} - {target.provider} - {target.source}
          </p>
          {target.tags.length ? (
            <p className="mt-1 text-xs text-zinc-500">{target.tags.slice(0, 3).join(', ')}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function RecentExecutions({ automation }: { automation: Automation }) {
  if (!automation.recent_executions.length) {
    return <p className="text-sm text-zinc-500">No execution history yet.</p>;
  }

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase text-zinc-500">Recent execution history</p>
      <div className="grid gap-2">
        {automation.recent_executions.map((execution) => (
          <div key={execution.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-200 px-3 py-2 text-sm">
            <div>
              <span className="font-semibold text-zinc-950">{formatLabel(execution.workflow_type)}</span>
              <span className="ml-2 text-zinc-500">{execution.target_nodes.join(', ') || execution.target_hostname || 'Unknown target'}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <RuntimeBadge value={execution.status} />
              <span className="text-xs text-zinc-500">{formatDurationSeconds(execution.duration_seconds)}</span>
              <span className="text-xs text-zinc-500">{formatDate(execution.started_at ?? execution.created_at)}</span>
            </div>
            {execution.error_message ? <p className="basis-full text-xs text-rose-700">{execution.error_message}</p> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function RuntimeFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-28 rounded-md bg-zinc-50 px-3 py-2">
      <div className="font-semibold uppercase">{label}</div>
      <div className="mt-1 text-zinc-800">{value}</div>
    </div>
  );
}

function RuntimeMetric({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="rounded-md border border-zinc-200 px-3 py-2">
      <Icon className="h-4 w-4 text-zinc-500" aria-hidden="true" />
      <div className="mt-2 text-xs font-semibold uppercase text-zinc-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Never';
}

function formatDurationSeconds(value: number | null): string {
  if (value == null) return 'Not measured';
  if (value < 60) return `${value}s`;
  return `${Math.floor(value / 60)}m ${value % 60}s`;
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNodeType(value: string): string {
  if (value === 'lxc') return 'LXC';
  if (value === 'vm') return 'VM';
  return formatLabel(value);
}

function toPayload(form: FormState): AutomationPayload | null {
  if (!form.name.trim() || !form.reference_id || form.target_server_ids.length === 0) return null;
  return {
    name: form.name.trim(),
    enabled: true,
    schedule_type: form.schedule_type,
    interval_seconds: form.schedule_type === 'interval' ? Number(form.interval_seconds) : null,
    cron_expression: form.schedule_type === 'cron' ? form.cron_expression.trim() : null,
    target_mode: form.target_server_ids.length > 1 ? 'multiple_hosts' : 'single_host',
    target_server_ids: form.target_server_ids,
    operation_type: form.operation_type,
    reference_id: form.reference_id,
    variables_json: {},
    credential_refs: {},
  };
}

````

## frontend/src/features/inventory/pages/HostDetailPage.tsx

``tsx
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Activity, Box, ExternalLink, HardDrive, Loader2, Play, Power, RefreshCw, RotateCw, ServerIcon, ShieldCheck, TerminalSquare } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { listAutomations } from '../../automations/api/automationsApi';
import type { Automation } from '../../automations/types/automation';
import { useAuth } from '../../auth/hooks/useAuth';
import { listDeployments } from '../../deployments/api/deploymentsApi';
import type { Deployment } from '../../deployments/types/deployment';
import { listLinuxGroups, listLinuxUsers, listSSHKeys } from '../../identity/api/identityApi';
import type { LinuxGroup, LinuxUser, SSHKey } from '../../identity/types/identity';
import { listJobs } from '../../jobs/api/jobsApi';
import type { Job } from '../../jobs/types/job';
import { getServerMetrics } from '../../monitoring/api/monitoringApi';
import type { ServerMetrics } from '../../monitoring/types/monitoring';
import { runVmAction } from '../../proxmox/api/proxmoxApi';
import type { ProxmoxVmAction } from '../../proxmox/types/proxmox';
import { FileBrowserPanel } from '../../remote-access/components/FileBrowserPanel';
import { ShellPanel } from '../../remote-access/components/ShellPanel';
import { RuntimeStateBadge } from '../../runtime-state/components/RuntimeStateBadge';
import { canRunLifecycleAction } from '../../runtime-state/utils/eligibility';
import { listWorkflows } from '../../workflows/api/workflowsApi';
import type { WorkflowRun } from '../../workflows/types/workflow';
import {
  getServer,
  getServerDocker,
  getServerNetwork,
  getServerSystem,
} from '../api/serversApi';
import type { HostDocker, HostNetwork, HostSystem, Server } from '../types/server';
import { EnvironmentBadge, HealthBadge, LifecycleBadge, SyncBadge } from '../components/ServerBadges';

type LoadState = {
  server: Server | null;
  system: HostSystem | null;
  network: HostNetwork | null;
  docker: HostDocker | null;
  metrics: ServerMetrics | null;
  deployments: Deployment[];
  jobs: Job[];
  workflows: WorkflowRun[];
  automations: Automation[];
  users: LinuxUser[];
  groups: LinuxGroup[];
  sshKeys: SSHKey[];
};

type HostTab = 'overview' | 'operations' | 'runtime' | 'access' | 'automation';

const initialState: LoadState = {
  server: null,
  system: null,
  network: null,
  docker: null,
  metrics: null,
  deployments: [],
  jobs: [],
  workflows: [],
  automations: [],
  users: [],
  groups: [],
  sshKeys: [],
};

export function HostDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [state, setState] = useState<LoadState>(initialState);
  const [errors, setErrors] = useState<string[]>([]);
  const [notice, setNotice] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);
  const [activeVmAction, setActiveVmAction] = useState<ProxmoxVmAction | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<HostTab>('overview');
  const allowManagement = user?.role === 'admin' || user?.role === 'operator';

  const refresh = useCallback(async () => {
    if (!id) {
      return;
    }
    setIsLoading(true);
    setErrors([]);

    const serverResult = await settle(() => getServer(id));
    if (!serverResult.ok) {
      setErrors([serverResult.error]);
      setIsLoading(false);
      return;
    }

    const [system, network, docker, metrics, deployments, jobs, workflows, automations, users, groups, sshKeys] =
      await Promise.all([
        settle(() => getServerSystem(id)),
        settle(() => getServerNetwork(id)),
        settle(() => getServerDocker(id)),
        settle(() => getServerMetrics(id)),
        settle(() => listDeployments({ serverId: id })),
        settle(() => listJobs({ targetServerId: id })),
        settle(() => listWorkflows({ targetServerId: id })),
        settle(() => listAutomations({ targetServerId: id })),
        settle(() => listLinuxUsers()),
        settle(() => listLinuxGroups()),
        settle(() => listSSHKeys()),
      ]);

    setState({
      server: serverResult.value,
      system: system.ok ? system.value : null,
      network: network.ok ? network.value : null,
      docker: docker.ok ? docker.value : null,
      metrics: metrics.ok ? metrics.value : null,
      deployments: deployments.ok ? deployments.value : [],
      jobs: jobs.ok ? jobs.value.slice(0, 8) : [],
      workflows: workflows.ok ? workflows.value.slice(0, 8) : [],
      automations: automations.ok ? automations.value.slice(0, 8) : [],
      users: users.ok ? users.value : [],
      groups: groups.ok ? groups.value : [],
      sshKeys: sshKeys.ok ? sshKeys.value : [],
    });
    setErrors(
      [system, network, docker, metrics, deployments, jobs, workflows, automations, users, groups, sshKeys]
        .filter((result) => !result.ok)
        .map((result) => (result.ok ? '' : result.error)),
    );
    setIsLoading(false);
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const exporterState = useMemo(() => detectExporters(state), [state]);

  async function handleVmLifecycle(action: ProxmoxVmAction) {
    const server = state.server;
    const vmId = getProviderVmId(server);
    if (!server || vmId === null) {
      setNotice({ tone: 'error', message: 'This inventory host is not linked to a Proxmox VMID.' });
      return;
    }

    if (action !== 'start') {
      const confirmed = window.confirm(`${actionLabel(action)} ${server.node_type === 'lxc' ? 'LXC' : 'VM'} ${server.hostname} (${vmId})?`);
      if (!confirmed) {
        return;
      }
    }

    setActiveVmAction(action);
    setNotice(null);
    try {
      const response = await runVmAction(vmId, action);
      setNotice({ tone: 'success', message: response.message });
      await refresh();
    } catch (caughtError) {
      setNotice({ tone: 'error', message: getApiErrorMessage(caughtError) });
    } finally {
      setActiveVmAction(null);
    }
  }

  if (isLoading && !state.server) {
    return <div className="h-80 animate-pulse rounded-lg bg-zinc-100" />;
  }

  if (!state.server) {
    return <ErrorPanel title="Host could not be loaded" errors={errors} onRetry={refresh} />;
  }

  const server = state.server;

  return (
    <div className="space-y-6">
      <PageHeader
        title={server.hostname}
        description="Unified operations for this managed node across inventory, provider, monitoring, remote access, jobs, deployments, and identity."
      />

      {notice ? <HostNotice message={notice.message} tone={notice.tone} onDismiss={() => setNotice(null)} /> : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <EnvironmentBadge environment={server.environment} />
          <LifecycleBadge state={server.lifecycle_state} />
          <SyncBadge status={server.sync_status} />
          <HealthBadge status={server.last_health_status} />
          <RuntimeStateBadge runtimeState={server.runtime_state} />
          <ReadinessBadge readiness={nodeReadiness(server, state)} />
          <NodeTypePill nodeType={server.node_type} />
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
          type="button"
          onClick={() => void refresh()}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
        <Link
          className="inline-flex items-center gap-2 rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800"
          to={`/inventory/${server.id}/tools`}
        >
          <TerminalSquare className="h-4 w-4" aria-hidden="true" />
          Host Tools
        </Link>
      </div>

      {errors.length ? <ErrorPanel title="Some live checks failed" errors={errors} onRetry={refresh} compact /> : null}

      <nav className="flex gap-2 overflow-x-auto rounded-lg border border-zinc-200 bg-white p-2 shadow-sm">
        {hostTabs.map((tab) => (
          <button
            key={tab.id}
            className={`whitespace-nowrap rounded-md px-3 py-2 text-sm font-semibold ${
              activeTab === tab.id ? 'bg-zinc-950 text-white' : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950'
            }`}
            type="button"
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab !== 'overview' ? (
        <HostTabPanel
          activeVmAction={activeVmAction}
          allowManagement={allowManagement}
          canUseRemoteAccess={allowManagement && Boolean(server.runtime_state?.eligibility.can_open_shell ?? true)}
          server={server}
          state={state}
          tab={activeTab}
          onVmLifecycle={(action) => void handleVmLifecycle(action)}
        />
      ) : null}

      {activeTab === 'overview' ? (
        <>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={ServerIcon} label="LAN IP" value={state.network?.lan_ip ?? server.ip_address} />
        <MetricCard icon={Activity} label="Uptime" value={formatDuration(state.system?.uptime_seconds ?? state.metrics?.uptime_seconds)} />
        <MetricCard icon={HardDrive} label="Memory" value={formatPercent(bytesPercent(state.system?.memory_used_bytes, state.system?.memory_total_bytes) ?? state.metrics?.memory_usage_percent)} />
        <MetricCard icon={Box} label="Readiness" value={formatReadiness(nodeReadiness(server, state))} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <OperationalInsightsPanel server={server} state={state} />

          <Panel title="System Overview">
            <dl className="grid gap-3 sm:grid-cols-2">
              <Info label="Node type" value={formatNodeType(server.node_type)} />
              <Info label="OS" value={state.system?.operating_system ?? server.operating_system} />
              <Info label="Kernel" value={state.system?.kernel ?? 'Unknown'} />
              <Info label="CPU" value={state.system?.cpu_model ?? 'Unknown'} />
              <Info label="Cores" value={state.system?.cpu_cores ? String(state.system.cpu_cores) : 'Unknown'} />
              <Info label="Load" value={state.system?.load_average.join(' / ') || 'Unknown'} />
              <Info label="Provider" value={`${server.provider}${server.provider_node ? ` / ${server.provider_node}` : ''}`} />
              <Info label="Lifecycle" value={server.lifecycle_state} />
              <Info label="Operational state" value={nodeReadiness(server, state)} />
              <Info label="SSH readiness" value={server.runtime_state?.ssh_state ?? sshReadiness(server, state)} />
              <Info label="Monitoring state" value={server.runtime_state?.monitoring_state ?? monitoringReadiness(state)} />
              <Info label="Provider state" value={server.runtime_state?.provider_state ?? 'unknown'} />
            </dl>
          </Panel>

          <ReconciliationPanel server={server} />

          <Panel title="Provider Metadata">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="Provider" value={server.provider} />
              <Info label="Provider type" value={server.provider_type ?? 'Unknown'} />
              <Info label="Provider node" value={server.provider_node ?? 'Unknown'} />
              <Info label="External ID" value={server.external_id ?? server.vmid ?? 'Unknown'} />
            </div>
            <MetadataBlock metadata={server.provider_metadata} />
          </Panel>

          <Panel title="Filesystems">
            <div className="grid gap-3 md:grid-cols-2">
              {(state.system?.filesystems ?? []).map((fs) => (
                <div key={`${fs.filesystem}-${fs.mountpoint}`} className="rounded-md border border-zinc-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-sm font-semibold text-zinc-950">{fs.mountpoint}</span>
                    <span className="text-xs text-zinc-500">{fs.type}</span>
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-zinc-100">
                    <div className="h-2 rounded-full bg-zinc-900" style={{ width: `${bytesPercent(fs.used_bytes, fs.size_bytes) ?? 0}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-zinc-500">{formatBytes(fs.used_bytes)} / {formatBytes(fs.size_bytes)}</p>
                </div>
              ))}
              {state.system?.filesystems.length === 0 ? <EmptyText text="No filesystem data collected." /> : null}
            </div>
          </Panel>

          <Panel title="Network">
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <h4 className="text-sm font-semibold text-zinc-950">Interfaces</h4>
                <div className="mt-3 space-y-2">
                  {(state.network?.interfaces ?? []).map((item) => (
                    <div key={item.name} className="rounded-md border border-zinc-200 p-3">
                      <div className="font-mono text-sm font-semibold">{item.name}</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {item.addresses.map((address) => (
                          <span key={address} className="rounded bg-zinc-100 px-2 py-1 font-mono text-xs text-zinc-700">{address}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                  {state.network?.interfaces.length === 0 ? <EmptyText text="No interfaces discovered." /> : null}
                </div>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-zinc-950">Listening Services</h4>
                <div className="mt-3 space-y-2">
                  {(state.network?.listening_ports ?? []).map((port) => (
                    <div key={`${port.protocol}-${port.address}-${port.port}`} className="flex items-center justify-between gap-3 rounded-md border border-zinc-200 p-3">
                      <div>
                        <div className="font-mono text-sm font-semibold">{port.port}/{port.protocol}</div>
                        <div className="text-xs text-zinc-500">{port.process ?? port.service ?? 'unknown process'}</div>
                      </div>
                      {serviceUrl(server.ip_address, port) ? (
                        <a className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-700 hover:text-zinc-950" href={serviceUrl(server.ip_address, port) ?? undefined} target="_blank" rel="noreferrer">
                          Open <ExternalLink className="h-3 w-3" aria-hidden="true" />
                        </a>
                      ) : null}
                    </div>
                  ))}
                  {state.network?.listening_ports.length === 0 ? <EmptyText text="No listening ports discovered." /> : null}
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="Docker Runtime">
            <div className="mb-4 flex flex-wrap gap-2">
              <Badge tone={state.docker?.installed ? 'success' : 'muted'}>{state.docker?.installed ? `Docker ${state.docker.version}` : 'Docker not detected'}</Badge>
              <Badge tone="muted">Restart quick actions planned</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-zinc-200 text-sm">
                <thead className="bg-zinc-50">
                  <tr>{['Container', 'Image', 'Status', 'Ports', 'Compose'].map((heading) => <th key={heading} className="px-3 py-2 text-left text-xs font-semibold uppercase text-zinc-500">{heading}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {(state.docker?.containers ?? []).map((container) => (
                    <tr key={container.container_id}>
                      <td className="px-3 py-2 font-semibold">{container.name}</td>
                      <td className="px-3 py-2 font-mono text-xs">{container.image}</td>
                      <td className="px-3 py-2"><Badge tone={container.status.toLowerCase().includes('up') ? 'success' : 'muted'}>{container.status}</Badge></td>
                      <td className="px-3 py-2 font-mono text-xs">{container.ports || '-'}</td>
                      <td className="px-3 py-2">{container.compose_project ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {state.docker?.containers.length === 0 ? <EmptyText text="No running containers discovered." /> : null}
            </div>
          </Panel>
        </div>

        <aside className="space-y-6">
          <Panel title="Monitoring">
            <div className="space-y-2">
              <Badge tone={state.metrics?.monitoring_state === 'monitored' ? 'success' : 'warning'}>
                {formatReadiness(state.metrics?.monitoring_state ?? monitoringReadiness(state))}
              </Badge>
              <Badge tone={state.metrics?.metrics_available ? 'success' : 'warning'}>metrics {state.metrics?.metrics_available ? 'available' : 'missing'}</Badge>
              <Badge tone={state.metrics?.logs_available ? 'success' : 'warning'}>logs {state.metrics?.logs_available ? 'available' : 'missing'}</Badge>
              <Badge tone={exporterState.node ? 'success' : 'muted'}>node_exporter {exporterState.node ? 'detected' : 'not detected'}</Badge>
              <Badge tone={exporterState.promtail ? 'success' : 'muted'}>promtail {exporterState.promtail ? 'detected' : 'not detected'}</Badge>
              <Badge tone={exporterState.cadvisor ? 'success' : 'muted'}>cadvisor {exporterState.cadvisor ? 'detected' : 'not detected'}</Badge>
              {state.metrics?.stale_metrics ? <Badge tone="warning">stale metrics</Badge> : null}
            </div>
            {state.metrics?.open_grafana_url ? (
              <a className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-zinc-800 hover:text-zinc-950" href={state.metrics.open_grafana_url} target="_blank" rel="noreferrer">
                Open Grafana <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
            ) : null}
          </Panel>

          <Panel title="Related Resources">
            <LinkList items={[
              { label: `${state.deployments.length} deployments`, to: '/deployments' },
              { label: `${state.jobs.length} recent jobs`, to: '/jobs' },
              { label: `${state.workflows.length} recent workflows`, to: '/workflows' },
              { label: `${state.automations.length} automations targeting node`, to: '/automations' },
              { label: `${state.users.length} users / ${state.groups.length} groups`, to: '/identity' },
              { label: `${state.sshKeys.length} SSH keys`, to: '/identity' },
            ]} />
          </Panel>

          <Panel title="Quick Actions">
            <LinkList items={[
              { label: 'Open dedicated host tools', to: `/inventory/${server.id}/tools` },
              { label: 'Run command', to: '/jobs' },
              { label: 'Apply profile', to: '/profiles' },
              { label: 'Deploy compose app', to: '/deployments' },
              { label: 'View monitoring', to: '/monitoring' },
            ]} />
          </Panel>

          <Panel title="Identity Scope">
            <div className="flex items-center gap-3 text-sm text-zinc-600">
              <ShieldCheck className="h-5 w-5 text-zinc-500" aria-hidden="true" />
              Linux identity orchestration is available through Jobs-backed replication.
            </div>
          </Panel>
        </aside>
      </section>
        </>
      ) : null}
    </div>
  );
}

const hostTabs: Array<{ id: HostTab; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'operations', label: 'Operations' },
  { id: 'runtime', label: 'Runtime' },
  { id: 'access', label: 'Access' },
  { id: 'automation', label: 'Automation' },
];

function HostTabPanel({
  activeVmAction,
  allowManagement,
  canUseRemoteAccess,
  tab,
  server,
  state,
  onVmLifecycle,
}: {
  activeVmAction: ProxmoxVmAction | null;
  allowManagement: boolean;
  canUseRemoteAccess: boolean;
  tab: HostTab;
  server: Server;
  state: LoadState;
  onVmLifecycle: (action: ProxmoxVmAction) => void;
}) {
  if (tab === 'operations') {
    return (
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel title="Lifecycle actions">
          <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <Info label="Provider" value={server.provider} />
            <Info label="Node" value={server.provider_node ?? 'Unknown'} />
            <Info label="VMID" value={String(getProviderVmId(server) ?? 'Not linked')} />
          </div>
          <VmLifecycleActions
            activeAction={activeVmAction}
            allowManagement={allowManagement}
            server={server}
            onAction={onVmLifecycle}
          />
          {!allowManagement ? <p className="text-sm text-zinc-500">Operator or admin role required for VM lifecycle actions.</p> : null}
          </div>
        </Panel>
        <EligibilityPanel server={server} />
      </div>
    );
  }

  if (tab === 'access') {
    return (
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="min-h-[520px]">
          <ShellPanel server={server} canUseShell={canUseRemoteAccess} compact />
        </div>
        <FileBrowserPanel server={server} canUseFiles={canUseRemoteAccess} />
      </div>
    );
  }

  if (tab === 'automation') {
    return (
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Deployments">
          <LinkList items={[
            ...state.deployments.map((deployment) => ({ label: `${deployment.name} - ${deployment.status}`, to: '/deployments' })),
            { label: 'Create deployment for this host', to: '/deployments' },
          ]} />
        </Panel>
        <Panel title="Jobs">
          <LinkList items={[
            ...state.jobs.map((job) => ({ label: `${job.operation_type} - ${job.status}`, to: '/jobs' })),
            { label: 'Run command for this host', to: '/jobs' },
          ]} />
        </Panel>
        <Panel title="Workflows and automations">
          <LinkList items={[
            ...state.workflows.map((workflow) => ({
              label: `${formatReadiness(workflow.workflow_type)} - ${workflow.status} - ${workflowProgress(workflow)}`,
              to: '/workflows',
            })),
            ...state.automations.map((automation) => ({
              label: `${automation.name} automation - ${automation.runtime_state}`,
              to: '/automations',
            })),
            { label: 'Open workflow history', to: '/workflows' },
          ]} />
        </Panel>
        <Panel title="Profiles and packages">
          <LinkList items={[
            { label: 'Run package against this host', to: '/packages' },
            { label: 'Apply profile to this host', to: '/profiles' },
          ]} />
        </Panel>
      </div>
    );
  }

  if (tab === 'runtime') {
    return (
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel title="Monitoring and freshness">
          <div className="grid gap-3 md:grid-cols-3">
            <Info label="Uptime" value={formatDuration(state.metrics?.uptime_seconds)} />
            <Info label="CPU" value={formatPercent(state.metrics?.cpu_usage_percent)} />
            <Info label="Memory" value={formatPercent(state.metrics?.memory_usage_percent)} />
            <Info label="Observability" value={formatReadiness(server.runtime_state?.observability_state ?? monitoringReadiness(state))} />
            <Info label="Runtime freshness" value={formatDateTime(server.runtime_state?.freshness.runtime_refreshed_at)} />
            <Info label="Confidence" value={formatReadiness(server.runtime_state?.freshness.confidence ?? 'unknown')} />
          </div>
        </Panel>
        <OperationalNoticesPanel server={server} />
      </div>
    );
  }

  return null;
}

function OperationalInsightsPanel({ server, state }: { server: Server; state: LoadState }) {
  const runtime = server.runtime_state;
  return (
    <Panel title="Operational insights">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="grid gap-3 sm:grid-cols-2">
          <Info label="Administrative state" value={formatReadiness(runtime?.administrative_state ?? server.lifecycle_state)} />
          <Info label="Infrastructure state" value={formatReadiness(runtime?.infrastructure_state ?? runtime?.provider_state ?? 'unknown')} />
          <Info label="Orchestration state" value={formatReadiness(runtime?.orchestration_state ?? nodeReadiness(server, state))} />
          <Info label="Observability state" value={formatReadiness(runtime?.observability_state ?? monitoringReadiness(state))} />
          <Info label="SSH readiness" value={formatReadiness(runtime?.ssh_state ?? sshReadiness(server, state))} />
          <Info label="Runtime readiness" value={formatReadiness(runtime?.readiness_state ?? nodeReadiness(server, state))} />
        </div>
        <OperationalNoticesPanel server={server} compact />
      </div>
    </Panel>
  );
}

function ReconciliationPanel({ server }: { server: Server }) {
  const reconciliation = server.runtime_state?.reconciliation;
  return (
    <Panel title="Reconciliation">
      <div className="grid gap-3 md:grid-cols-2">
        <Info label="Provider link" value={formatReadiness(reconciliation?.provider_link_status ?? providerLinkStatus(server))} />
        <Info label="Confidence" value={formatReadiness(reconciliation?.confidence ?? 'unknown')} />
        <Info label="Provider sync" value={formatReadiness(reconciliation?.provider_sync_freshness ?? server.sync_state)} />
        <Info label="Last reconciled" value={formatDateTime(reconciliation?.last_reconciled_at ?? server.last_sync_at ?? server.last_seen_at)} />
      </div>
      <NoticeList
        emptyText="No reconciliation drift detected."
        items={[...(reconciliation?.drift_indicators ?? []), ...(reconciliation?.mismatch_explanations ?? [])]}
      />
    </Panel>
  );
}

function EligibilityPanel({ server }: { server: Server }) {
  const eligibility = server.runtime_state?.eligibility;
  const actions = [
    ['can_open_shell', 'Shell'],
    ['can_run_jobs', 'Jobs'],
    ['can_deploy', 'Deployments'],
    ['can_apply_profiles', 'Profiles'],
    ['can_manage_identity', 'Identity'],
    ['can_start', 'Start'],
    ['can_stop', 'Stop'],
    ['can_reboot', 'Reboot'],
    ['can_sync_provider', 'Provider sync'],
  ] as const;
  return (
    <Panel title="Runtime eligibility">
      <div className="space-y-3">
        {actions.map(([key, label]) => {
          const allowed = Boolean(eligibility?.[key] ?? false);
          const blockers = eligibility?.blockers?.[key] ?? [];
          return (
            <div key={key} className="rounded-md border border-zinc-200 p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-zinc-950">{label}</span>
                <Badge tone={allowed ? 'success' : 'warning'}>{allowed ? 'Allowed' : 'Blocked'}</Badge>
              </div>
              {!allowed ? <p className="mt-2 text-xs text-zinc-500">{blockers.map(formatReadiness).join(', ') || 'Policy not satisfied'}</p> : null}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function OperationalNoticesPanel({ server, compact = false }: { server: Server; compact?: boolean }) {
  const runtime = server.runtime_state;
  const items = [
    ...(runtime?.degraded_reasons ?? []),
    ...(runtime?.stale_reasons ?? []),
    ...(runtime?.warnings ?? []),
  ];
  return (
    <div className={compact ? '' : 'space-y-4'}>
      <NoticeList emptyText="No runtime warnings reported." items={items} />
      {!compact ? (
        <div className="grid gap-3">
          <Info label="Provider refresh" value={formatDateTime(runtime?.freshness.provider_refreshed_at)} />
          <Info label="Monitoring refresh" value={formatDateTime(runtime?.freshness.monitoring_refreshed_at)} />
          <Info label="Inventory refresh" value={formatDateTime(runtime?.freshness.inventory_refreshed_at)} />
        </div>
      ) : null}
    </div>
  );
}

function NoticeList({ emptyText, items }: { emptyText: string; items: string[] }) {
  const uniqueItems = Array.from(new Set(items.filter(Boolean)));
  if (!uniqueItems.length) {
    return <EmptyText text={emptyText} />;
  }
  return (
    <div className="mt-4 space-y-2">
      {uniqueItems.map((item) => (
        <div key={item} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {formatReadiness(item)}
        </div>
      ))}
    </div>
  );
}

function HostNotice({
  message,
  tone,
  onDismiss,
}: {
  message: string;
  tone: 'success' | 'error';
  onDismiss: () => void;
}) {
  const className =
    tone === 'success'
      ? 'border-emerald-400/30 bg-emerald-950/40 text-emerald-100'
      : 'border-rose-400/30 bg-rose-950/50 text-rose-100';
  return (
    <div className={`flex items-center justify-between gap-4 rounded-lg border px-4 py-3 ${className}`}>
      <p className="text-sm font-medium">{message}</p>
      <button className="text-sm font-semibold underline-offset-2 hover:underline" type="button" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}

function ReadinessBadge({ readiness }: { readiness: string }) {
  const tone =
    readiness === 'healthy' || readiness === 'booted'
      ? 'success'
      : readiness === 'degraded' ||
          readiness === 'ssh_unreachable' ||
          readiness === 'network_missing' ||
          readiness === 'monitoring_missing' ||
          readiness === 'partially_managed'
        ? 'warning'
        : 'muted';
  return <Badge tone={tone}>{formatReadiness(readiness)}</Badge>;
}

function NodeTypePill({ nodeType }: { nodeType: Server['node_type'] }) {
  const className =
    nodeType === 'hypervisor'
      ? 'bg-violet-50 text-violet-700 ring-violet-200'
      : nodeType === 'lxc'
        ? 'bg-cyan-50 text-cyan-700 ring-cyan-200'
        : nodeType === 'vm'
          ? 'bg-indigo-50 text-indigo-700 ring-indigo-200'
          : 'bg-zinc-100 text-zinc-700 ring-zinc-200';
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}>
      {formatNodeType(nodeType)}
    </span>
  );
}

function MetadataBlock({ metadata }: { metadata: Record<string, unknown> }) {
  const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined && value !== '');
  if (!entries.length) {
    return <EmptyText text="No provider metadata recorded." />;
  }
  return (
    <dl className="mt-4 grid gap-3 md:grid-cols-2">
      {entries.slice(0, 12).map(([key, value]) => (
        <Info key={key} label={key.replace(/_/g, ' ')} value={metadataValue(value)} />
      ))}
    </dl>
  );
}

function VmLifecycleActions({
  activeAction,
  allowManagement,
  server,
  onAction,
}: {
  activeAction: ProxmoxVmAction | null;
  allowManagement: boolean;
  server: Server;
  onAction: (action: ProxmoxVmAction) => void;
}) {
  const vmId = getProviderVmId(server);
  const isBusy = activeAction !== null;
  const isLinkedProxmoxVm = server.provider === 'proxmox' && vmId !== null;
  const commonDisabled = !allowManagement || !isLinkedProxmoxVm || isBusy;
  const canStart = canRunLifecycleAction(server.runtime_state, 'start') || (!server.runtime_state && isLinkedProxmoxVm);
  const canStop = canRunLifecycleAction(server.runtime_state, 'stop') || (!server.runtime_state && (server.status === 'online' || server.last_health_status === 'online'));
  const canReboot = canRunLifecycleAction(server.runtime_state, 'reboot') || (!server.runtime_state && (server.status === 'online' || server.last_health_status === 'online'));

  return (
    <div className="flex flex-wrap gap-2">
      <LifecycleButton
        action="start"
        disabled={commonDisabled || !canStart}
        icon={Play}
        isLoading={activeAction === 'start'}
        label="Start"
        tone="primary"
        onClick={() => onAction('start')}
      />
      <LifecycleButton
        action="shutdown"
        disabled={commonDisabled || !canStop}
        icon={Power}
        isLoading={activeAction === 'shutdown'}
        label="Shutdown"
        onClick={() => onAction('shutdown')}
      />
      <LifecycleButton
        action="reboot"
        disabled={commonDisabled || !canReboot}
        icon={RotateCw}
        isLoading={activeAction === 'reboot'}
        label="Reboot"
        onClick={() => onAction('reboot')}
      />
      <LifecycleButton
        action="stop"
        disabled={commonDisabled || !canStop}
        icon={Power}
        isLoading={activeAction === 'stop'}
        label="Stop"
        tone="danger"
        onClick={() => onAction('stop')}
      />
    </div>
  );
}

function LifecycleButton({
  disabled,
  icon: Icon,
  isLoading,
  label,
  onClick,
  tone = 'secondary',
}: {
  action: ProxmoxVmAction;
  disabled: boolean;
  icon: typeof Play;
  isLoading: boolean;
  label: string;
  onClick: () => void;
  tone?: 'primary' | 'secondary' | 'danger';
}) {
  const className =
    tone === 'primary'
      ? 'border-cyan-400 bg-cyan-400 text-zinc-950 hover:bg-cyan-300 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
      : tone === 'danger'
        ? 'border-rose-400/50 bg-white text-rose-700 hover:bg-rose-50 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
        : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 disabled:bg-zinc-100 disabled:text-zinc-400';
  return (
    <button
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${className}`}
      disabled={disabled}
      type="button"
      onClick={onClick}
    >
      {isLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Icon className="h-4 w-4" aria-hidden="true" />}
      {label}
    </button>
  );
}

function getProviderVmId(server: Server | null): number | null {
  const raw = server?.vmid ?? server?.external_id ?? null;
  if (!raw) {
    return null;
  }
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function actionLabel(action: ProxmoxVmAction): string {
  return action.charAt(0).toUpperCase() + action.slice(1);
}

async function settle<T>(fn: () => Promise<T>): Promise<{ ok: true; value: T } | { ok: false; error: string }> {
  try {
    return { ok: true, value: await fn() };
  } catch (error) {
    return { ok: false, error: getApiErrorMessage(error) };
  }
}

function workflowProgress(workflow: WorkflowRun): string {
  if (!workflow.steps.length) {
    return 'no steps';
  }
  const failed = workflow.failed_steps ? `, ${workflow.failed_steps} failed` : '';
  return `${workflow.completed_steps}/${workflow.steps.length} completed${failed}`;
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function MetricCard({ icon: Icon, label, value }: { icon: typeof ServerIcon; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <Icon className="h-5 w-5 text-zinc-500" aria-hidden="true" />
      <div className="mt-3 text-sm text-zinc-500">{label}</div>
      <div className="mt-1 break-words text-xl font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase text-zinc-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-zinc-900">{value}</dd>
    </div>
  );
}

function Badge({ children, tone }: { children: ReactNode; tone: 'success' | 'warning' | 'muted' }) {
  const className = {
    success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    warning: 'bg-amber-50 text-amber-700 ring-amber-200',
    muted: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
  }[tone];
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}>{children}</span>;
}

function EmptyText({ text }: { text: string }) {
  return <p className="py-3 text-sm text-zinc-500">{text}</p>;
}

function LinkList({ items }: { items: Array<{ label: string; to: string }> }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <Link key={item.label} className="flex items-center justify-between rounded-md border border-zinc-200 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" to={item.to}>
          {item.label}
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
        </Link>
      ))}
    </div>
  );
}

function ErrorPanel({ title, errors, onRetry, compact = false }: { title: string; errors: string[]; onRetry: () => void; compact?: boolean }) {
  return (
    <div className={`rounded-lg border border-amber-200 bg-amber-50 text-amber-900 ${compact ? 'p-3' : 'p-5'}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold">{title}</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {errors.map((error) => <li key={error}>{error}</li>)}
          </ul>
        </div>
        <button className="rounded-md bg-amber-700 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-800" type="button" onClick={onRetry}>Retry</button>
      </div>
    </div>
  );
}

function formatBytes(value: number | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let next = value;
  let index = 0;
  while (next >= 1024 && index < units.length - 1) {
    next /= 1024;
    index += 1;
  }
  return `${next.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function bytesPercent(used: number | null | undefined, total: number | null | undefined): number | null {
  if (!used || !total) {
    return null;
  }
  return Math.round((used / total) * 100);
}

function formatPercent(value: number | null | undefined): string {
  return value == null ? 'Unknown' : `${Math.round(value)}%`;
}

function nodeReadiness(server: Server, state: LoadState): string {
  if (server.runtime_state) {
    if (server.runtime_state.degraded_reasons.length) {
      return 'degraded';
    }
    return server.runtime_state.orchestration_state;
  }
  const metadataReadiness = String(server.provider_metadata.operational_readiness ?? '').trim();
  if (metadataReadiness) {
    if (state.metrics?.monitoring_state === 'unmonitored' && metadataReadiness === 'booted') {
      return 'monitoring_missing';
    }
    return metadataReadiness;
  }
  if (server.lifecycle_state === 'archived' || server.lifecycle_state === 'decommissioned') {
    return server.lifecycle_state;
  }
  if (!server.ip_address || server.ip_address.startsWith('0.')) {
    return 'ip_missing';
  }
  if (state.system || state.network) {
    return state.metrics?.monitoring_state === 'unmonitored' ? 'monitoring_missing' : 'healthy';
  }
  if (server.last_health_status === 'unreachable') {
    return 'ssh_unreachable';
  }
  if (server.last_health_status === 'sync_error') {
    return 'degraded';
  }
  return server.managed ? 'partially_managed' : 'discovered';
}

function sshReadiness(server: Server, state: LoadState): string {
  if (state.system || state.network) {
    return 'ready';
  }
  if (!server.ip_address || server.ip_address.startsWith('0.')) {
    return 'ip_missing';
  }
  if (server.last_health_status === 'unreachable') {
    return 'ssh_unreachable';
  }
  return server.credential_id || server.ssh_username ? 'not_verified' : 'credential_missing';
}

function monitoringReadiness(state: LoadState): string {
  return state.metrics?.monitoring_state ?? 'unknown';
}

function providerLinkStatus(server: Server): string {
  if (server.provider !== 'proxmox') {
    return 'not_provider_backed';
  }
  if (server.sync_state === 'orphaned') {
    return 'provider_guest_missing';
  }
  return server.vmid || server.external_id ? 'linked' : 'missing_provider_identity';
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown';
  }
  return date.toLocaleString();
}

function formatReadiness(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ') || 'Unknown';
}

function formatNodeType(value: Server['node_type']): string {
  if (value === 'lxc') return 'LXC';
  if (value === 'vm') return 'VM';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function metadataValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => metadataValue(item)).join(', ') : 'None';
  }
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value);
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return String(value);
}

function formatDuration(value: number | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  return days ? `${days}d ${hours}h` : `${hours}h`;
}

function serviceUrl(host: string, port: { port: number; service: string | null; protocol: string }): string | null {
  if (port.service === 'http' || port.port === 80) {
    return `http://${host}`;
  }
  if (port.service === 'https' || port.port === 443) {
    return `https://${host}`;
  }
  if ([3000, 8000, 9090].includes(port.port)) {
    return `http://${host}:${port.port}`;
  }
  return null;
}

function detectExporters(state: LoadState) {
  const processes = (state.network?.listening_ports ?? []).map((port) => `${port.process ?? ''} ${port.port}`).join(' ').toLowerCase();
  const containers = (state.docker?.containers ?? []).map((container) => `${container.name} ${container.image}`).join(' ').toLowerCase();
  return {
    node: processes.includes('9100') || containers.includes('node-exporter') || containers.includes('node_exporter'),
    promtail: containers.includes('promtail') || processes.includes('promtail'),
    cadvisor: containers.includes('cadvisor') || processes.includes('8080'),
  };
}

````

