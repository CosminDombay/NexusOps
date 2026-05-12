import type { ServerEnvironment, ServerStatus } from '../types/server';
import { environmentStyles, formatLabel, statusStyles } from '../utils/options';

type BadgeProps = {
  children: string;
  className: string;
};

function Badge({ children, className }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${className}`}>
      {children}
    </span>
  );
}

export function EnvironmentBadge({ environment }: { environment: ServerEnvironment }) {
  return <Badge className={environmentStyles[environment]}>{formatLabel(environment)}</Badge>;
}

export function StatusBadge({ status }: { status: ServerStatus }) {
  return <Badge className={statusStyles[status]}>{formatLabel(status)}</Badge>;
}
