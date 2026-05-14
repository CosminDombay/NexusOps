/**
 * Centralized constant definitions matching backend enums.
 * 
 * Keep these synchronized with backend/app/common/constants.py
 */

export const ServerStatus = {
  UNKNOWN: 'unknown',
  ONLINE: 'online',
  OFFLINE: 'offline',
  MAINTENANCE: 'maintenance',
} as const;

export type ServerStatus = (typeof ServerStatus)[keyof typeof ServerStatus];

export const ServerEnvironment = {
  DEVELOPMENT: 'development',
  STAGING: 'staging',
  PRODUCTION: 'production',
  TESTING: 'testing',
  LAB: 'lab',
} as const;

export type ServerEnvironment = (typeof ServerEnvironment)[keyof typeof ServerEnvironment];

export const ServerSshAuthMethod = {
  KEY: 'key',
  PASSWORD: 'password',
} as const;

export type ServerSshAuthMethod = (typeof ServerSshAuthMethod)[keyof typeof ServerSshAuthMethod];

export const InventoryLifecycleState = {
  DISCOVERED: 'discovered',
  UNMANAGED: 'unmanaged',
  MANAGED: 'managed',
  PROVISIONED: 'provisioned',
  ARCHIVED: 'archived',
} as const;

export type InventoryLifecycleState = (typeof InventoryLifecycleState)[keyof typeof InventoryLifecycleState];

export const InventorySyncStatus = {
  UNKNOWN: 'unknown',
  SYNCED: 'synced',
  UNMANAGED: 'unmanaged',
  ORPHANED: 'orphaned',
  MISMATCH: 'mismatch',
  ARCHIVED: 'archived',
} as const;

export type InventorySyncStatus = (typeof InventorySyncStatus)[keyof typeof InventorySyncStatus];

/** Default values for new inventory entries */
export const INVENTORY_DEFAULTS = {
  status: ServerStatus.UNKNOWN,
  lifecycleState: InventoryLifecycleState.MANAGED,
  syncStatus: InventorySyncStatus.UNKNOWN,
  environment: ServerEnvironment.LAB,
  sshPort: 22,
  sshAuthMethod: ServerSshAuthMethod.KEY,
  managed: true,
  source: 'manual',
} as const;

/** Display labels for states */
export const STATE_LABELS = new Map<string, string>([
  // Server status
  [ServerStatus.UNKNOWN, 'Unknown'],
  [ServerStatus.ONLINE, 'Online'],
  [ServerStatus.OFFLINE, 'Offline'],
  [ServerStatus.MAINTENANCE, 'Maintenance'],

  // Lifecycle states
  [InventoryLifecycleState.DISCOVERED, 'Discovered'],
  [InventoryLifecycleState.UNMANAGED, 'Unmanaged'],
  [InventoryLifecycleState.MANAGED, 'Managed'],
  [InventoryLifecycleState.PROVISIONED, 'Provisioned'],
  [InventoryLifecycleState.ARCHIVED, 'Archived'],

  // Sync statuses
  [InventorySyncStatus.UNKNOWN, 'Unknown'],
  [InventorySyncStatus.SYNCED, 'Synced'],
  [InventorySyncStatus.UNMANAGED, 'Unmanaged'],
  [InventorySyncStatus.ORPHANED, 'Orphaned'],
  [InventorySyncStatus.MISMATCH, 'Mismatch'],
  [InventorySyncStatus.ARCHIVED, 'Archived'],
]);

/** Get display label for a state value */
export function getStateLabel(value: string | null | undefined): string {
  if (!value) return 'Unknown';
  return STATE_LABELS.get(value) ?? value.charAt(0).toUpperCase() + value.slice(1);
}
