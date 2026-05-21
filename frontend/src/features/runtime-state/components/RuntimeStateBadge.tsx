import { RuntimeBadge } from '../../../components/operations/OperationalComponents';
import type { NodeRuntimeState } from '../types/runtimeState';

export function RuntimeStateBadge({ runtimeState }: { runtimeState: NodeRuntimeState | null | undefined }) {
  if (!runtimeState) {
    return <RuntimeBadge value="unknown" />;
  }
  if (runtimeState.degraded_reasons.length > 0) {
    return <RuntimeBadge value="degraded" />;
  }
  if (runtimeState.orchestration_state === 'ready') {
    return <RuntimeBadge value="ready" />;
  }
  return <RuntimeBadge value={runtimeState.orchestration_state} />;
}
