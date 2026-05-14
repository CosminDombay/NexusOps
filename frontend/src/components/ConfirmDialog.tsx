import { AlertCircle, CheckCircle, Trash2, Archive } from 'lucide-react';

type ConfirmDialogProps = {
  isOpen: boolean;
  title: string;
  message: string;
  actionLabel: string;
  cancelLabel?: string;
  tone?: 'danger' | 'warning' | 'info';
  icon?: 'trash' | 'archive' | 'alert' | 'check';
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
};

export function ConfirmDialog({
  isOpen,
  title,
  message,
  actionLabel,
  cancelLabel = 'Cancel',
  tone = 'danger',
  icon,
  onConfirm,
  onCancel,
  isLoading = false,
}: ConfirmDialogProps) {
  if (!isOpen) return null;

  const IconComponent =
    icon === 'trash'
      ? Trash2
      : icon === 'archive'
        ? Archive
        : icon === 'check'
          ? CheckCircle
          : AlertCircle;

  const iconColor =
    tone === 'danger'
      ? 'text-rose-600'
      : tone === 'warning'
        ? 'text-amber-600'
        : 'text-blue-600';

  const actionButtonColor =
    tone === 'danger'
      ? 'border-rose-300 bg-white text-rose-700 hover:bg-rose-50 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
      : tone === 'warning'
        ? 'border-amber-300 bg-white text-amber-700 hover:bg-amber-50 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400'
        : 'border-blue-300 bg-white text-blue-700 hover:bg-blue-50 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400';

  async function handleConfirm() {
    const result = onConfirm();
    if (result instanceof Promise) {
      await result;
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative w-full max-w-md rounded-lg bg-white shadow-xl">
        {/* Body */}
        <div className="p-6">
          <div className="flex gap-4">
            <div className="shrink-0">
              <IconComponent className={`h-6 w-6 ${iconColor}`} aria-hidden="true" />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-zinc-950">{title}</h2>
              <p className="mt-2 text-sm text-zinc-600">{message}</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-3">
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:bg-zinc-100 disabled:text-zinc-400"
            >
              {cancelLabel}
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={isLoading}
              className={`rounded-md border px-4 py-2 text-sm font-semibold transition ${actionButtonColor}`}
            >
              {isLoading ? 'Processing...' : actionLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
