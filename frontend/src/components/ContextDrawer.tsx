import type { ReactNode } from 'react';
import { X } from 'lucide-react';

type ContextDrawerProps = {
  isOpen: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  width?: 'md' | 'lg' | 'xl';
  onClose: () => void;
};

const widthClass = {
  md: 'w-[min(100%,36rem)]',
  lg: 'w-[min(100%,48rem)]',
  xl: 'w-[min(100%,56rem)]',
};

export function ContextDrawer({
  isOpen,
  title,
  description,
  children,
  width = 'lg',
  onClose,
}: ContextDrawerProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-zinc-950/40 p-3 sm:p-5">
      <aside
        className={`mx-auto flex h-full ${widthClass[width]} max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-md bg-white shadow-xl sm:max-w-[calc(100vw-2.5rem)]`}
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-zinc-200 p-5">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-zinc-950">{title}</h2>
            {description ? <p className="mt-1 text-sm text-zinc-500">{description}</p> : null}
          </div>
          <button
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-zinc-300 text-zinc-600 hover:bg-zinc-50"
            type="button"
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Close drawer</span>
          </button>
        </div>
        <div className="min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-5">{children}</div>
      </aside>
    </div>
  );
}
