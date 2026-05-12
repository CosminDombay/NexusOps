import { statusClassName, titleCase } from '../utils/format';

type StatusBadgeProps = {
  status: string;
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${statusClassName(
        status,
      )}`}
    >
      {titleCase(status)}
    </span>
  );
}
