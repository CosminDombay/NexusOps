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
