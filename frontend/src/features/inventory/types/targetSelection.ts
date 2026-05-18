export type TargetSelectionMode = 'single' | 'bulk';

export type TargetSelection = {
  mode: TargetSelectionMode;
  selectedId: string;
  selectedIds: string[];
};

export type TargetFilters = {
  search: string;
  environment: string;
  provider: string;
  managed: 'all' | 'managed' | 'unmanaged';
};

export function selectedTargetIds(selection: TargetSelection): string[] {
  if (selection.mode === 'bulk') {
    return selection.selectedIds;
  }
  return selection.selectedId ? [selection.selectedId] : [];
}
