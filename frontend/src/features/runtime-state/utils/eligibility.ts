import type { ProxmoxVmAction } from '../../proxmox/types/proxmox';
import type { NodeRuntimeState } from '../types/runtimeState';

export function canRunLifecycleAction(runtimeState: NodeRuntimeState | null | undefined, action: ProxmoxVmAction): boolean {
  if (!runtimeState) {
    return false;
  }
  if (action === 'start') {
    return runtimeState.eligibility.can_start;
  }
  if (action === 'stop' || action === 'shutdown') {
    return runtimeState.eligibility.can_stop;
  }
  if (action === 'reboot') {
    return runtimeState.eligibility.can_reboot;
  }
  return false;
}
