import type {
  InventoryHealthStatus,
  InventoryLifecycleState,
  InventorySyncStatus,
  ManagedNodeType,
  ManagementState,
  ServerEnvironment,
  ServerStatus,
} from '../types/server';
import {
  environmentStyles,
  formatLabel,
  healthStyles,
  lifecycleStyles,
  managementStyles,
  nodeTypeStyles,
  statusStyles,
  syncStyles,
} from '../utils/options';

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

export function LifecycleBadge({ state }: { state: InventoryLifecycleState }) {
  return <Badge className={lifecycleStyles[state]}>{formatLabel(state)}</Badge>;
}

export function NodeTypeBadge({ nodeType }: { nodeType: ManagedNodeType }) {
  return <Badge className={nodeTypeStyles[nodeType]}>{formatLabel(nodeType)}</Badge>;
}

export function ManagementBadge({ state }: { state: ManagementState }) {
  return <Badge className={managementStyles[state]}>{formatLabel(state)}</Badge>;
}

export function SyncBadge({ status }: { status: InventorySyncStatus }) {
  return <Badge className={syncStyles[status]}>{formatLabel(status)}</Badge>;
}

export function HealthBadge({ status }: { status: InventoryHealthStatus }) {
  return <Badge className={healthStyles[status]}>{formatLabel(status)}</Badge>;
}
