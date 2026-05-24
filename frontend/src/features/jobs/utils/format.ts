import type { JobStatus } from '../types/job';
import { formatDateTime, formatOperationalLabel } from '../../../components/operations/runtimeFormat';

export { formatDateTime };

export function jobStatusLabel(status: JobStatus): string {
  return formatOperationalLabel(status);
}
