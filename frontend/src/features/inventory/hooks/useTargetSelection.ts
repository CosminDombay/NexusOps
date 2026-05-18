import { useMemo, useState } from 'react';

import type { Server } from '../types/server';
import type { TargetFilters, TargetSelection, TargetSelectionMode } from '../types/targetSelection';

const initialFilters: TargetFilters = {
  search: '',
  environment: 'all',
  provider: 'all',
  managed: 'all',
};

export function useTargetSelection(defaultMode: TargetSelectionMode = 'single') {
  const [selection, setSelection] = useState<TargetSelection>({
    mode: defaultMode,
    selectedId: '',
    selectedIds: [],
  });
  const [filters, setFilters] = useState<TargetFilters>(initialFilters);

  return {
    selection,
    filters,
    setMode: (mode: TargetSelectionMode) => setSelection((current) => ({ ...current, mode })),
    setSelectedId: (selectedId: string) => setSelection((current) => ({ ...current, selectedId })),
    setSelectedIds: (selectedIds: string[]) => setSelection((current) => ({ ...current, selectedIds })),
    setFilters,
    clear: () => setSelection((current) => ({ ...current, selectedId: '', selectedIds: [] })),
  };
}

export function useFilteredTargets(servers: Server[], filters: TargetFilters) {
  return useMemo(
    () =>
      servers.filter((server) => {
        const search = filters.search.trim().toLowerCase();
        const matchesSearch =
          !search ||
          `${server.hostname} ${server.ip_address} ${server.environment} ${server.provider} ${server.lifecycle_state}`
            .toLowerCase()
            .includes(search);
        const matchesEnvironment =
          filters.environment === 'all' || server.environment === filters.environment;
        const matchesProvider = filters.provider === 'all' || server.provider === filters.provider;
        const matchesManaged =
          filters.managed === 'all' ||
          (filters.managed === 'managed' ? server.managed : !server.managed);
        return matchesSearch && matchesEnvironment && matchesProvider && matchesManaged;
      }),
    [filters, servers],
  );
}
