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
            <p className="mt-2 text-sm text-zinc-500">Duration {formatDuration(job)} · Exit {job.exit_code ?? '-'}</p>
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
