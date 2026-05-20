import { useCallback, useEffect, useState } from 'react';

import { getApiErrorMessage } from '../../../lib/api/client';
import { decommissionServer, deleteServer, importProxmoxVm, reconcileProxmoxInventory, restoreServer } from '../../inventory/api/serversApi';
import type { ImportProxmoxVmPayload } from '../../inventory/types/server';
import { getProxmoxDashboard, runVmAction, syncProxmoxGuests, syncProxmoxHosts } from '../api/proxmoxApi';
import type { ProxmoxDashboard, ProxmoxVmAction } from '../types/proxmox';

type ProxmoxNotification = {
  tone: 'success' | 'error';
  message: string;
};

type UseProxmoxDashboardResult = {
  dashboard: ProxmoxDashboard | null;
  isLoading: boolean;
  error: string | null;
  actionByVmId: Record<number, ProxmoxVmAction | undefined>;
  notification: ProxmoxNotification | null;
  refreshDashboard: () => Promise<void>;
  runAction: (vmId: number, action: ProxmoxVmAction) => Promise<void>;
  importVm: (payload: ImportProxmoxVmPayload) => Promise<void>;
  reconcileInventory: () => Promise<void>;
  syncHosts: () => Promise<void>;
  syncGuests: () => Promise<void>;
  decommissionHost: (serverId: string) => Promise<void>;
  restoreHost: (serverId: string) => Promise<void>;
  removeHostRecord: (serverId: string) => Promise<void>;
  clearNotification: () => void;
};

export function useProxmoxDashboard(): UseProxmoxDashboardResult {
  const [dashboard, setDashboard] = useState<ProxmoxDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionByVmId, setActionByVmId] = useState<Record<number, ProxmoxVmAction | undefined>>({});
  const [notification, setNotification] = useState<ProxmoxNotification | null>(null);

  const refreshDashboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      setDashboard(await getProxmoxDashboard());
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshDashboard();
  }, [refreshDashboard]);

  const runAction = useCallback(
    async (vmId: number, action: ProxmoxVmAction) => {
      setActionByVmId((current) => ({ ...current, [vmId]: action }));
      setNotification(null);

      try {
        const response = await runVmAction(vmId, action);
        setNotification({ tone: 'success', message: response.message });
        await refreshDashboard();
      } catch (caughtError) {
        setNotification({ tone: 'error', message: getApiErrorMessage(caughtError) });
      } finally {
        setActionByVmId((current) => {
          const next = { ...current };
          delete next[vmId];
          return next;
        });
      }
    },
    [refreshDashboard],
  );

  const importVm = useCallback(
    async (payload: ImportProxmoxVmPayload) => {
      setNotification(null);

      try {
        const server = await importProxmoxVm(payload);
        setNotification({ tone: 'success', message: `${server.hostname} imported to Inventory.` });
        await refreshDashboard();
      } catch (caughtError) {
        setNotification({ tone: 'error', message: getApiErrorMessage(caughtError) });
      }
    },
    [refreshDashboard],
  );

  const reconcileInventory = useCallback(async () => {
    setNotification(null);

    try {
      await reconcileProxmoxInventory();
      setNotification({ tone: 'success', message: 'Inventory reconciliation completed.' });
      await refreshDashboard();
    } catch (caughtError) {
      setNotification({ tone: 'error', message: getApiErrorMessage(caughtError) });
    }
  }, [refreshDashboard]);

  const syncHosts = useCallback(async () => {
    setNotification(null);

    try {
      const result = await syncProxmoxHosts();
      setNotification({
        tone: 'success',
        message: `${result.imported_count} Proxmox host(s) imported, ${result.updated_count} updated, ${result.skipped_count} skipped.`,
      });
      await refreshDashboard();
    } catch (caughtError) {
      setNotification({ tone: 'error', message: getApiErrorMessage(caughtError) });
    }
  }, [refreshDashboard]);

  const syncGuests = useCallback(async () => {
    setNotification(null);

    try {
      const result = await syncProxmoxGuests();
      setNotification({
        tone: 'success',
        message: `${result.imported_count} Proxmox guest(s) imported, ${result.updated_count} updated, ${result.skipped_count} skipped.`,
      });
      await refreshDashboard();
    } catch (caughtError) {
      setNotification({ tone: 'error', message: getApiErrorMessage(caughtError) });
    }
  }, [refreshDashboard]);

  const decommissionHost = useCallback(
    async (serverId: string) => {
      setNotification(null);
      try {
        const server = await decommissionServer(serverId);
        setNotification({ tone: 'success', message: `${server.hostname} disconnected from active NexusOps orchestration.` });
        await refreshDashboard();
      } catch (caughtError) {
        setNotification({ tone: 'error', message: getApiErrorMessage(caughtError) });
      }
    },
    [refreshDashboard],
  );

  const restoreHost = useCallback(
    async (serverId: string) => {
      setNotification(null);
      try {
        const server = await restoreServer(serverId);
        setNotification({ tone: 'success', message: `${server.hostname} reconnected to active NexusOps orchestration.` });
        await refreshDashboard();
      } catch (caughtError) {
        setNotification({ tone: 'error', message: getApiErrorMessage(caughtError) });
      }
    },
    [refreshDashboard],
  );

  const removeHostRecord = useCallback(
    async (serverId: string) => {
      setNotification(null);
      try {
        await deleteServer(serverId);
        setNotification({ tone: 'success', message: 'Hypervisor inventory record removed. Sync the integration to rediscover it.' });
        await refreshDashboard();
      } catch (caughtError) {
        setNotification({ tone: 'error', message: getApiErrorMessage(caughtError) });
      }
    },
    [refreshDashboard],
  );

  return {
    dashboard,
    isLoading,
    error,
    actionByVmId,
    notification,
    refreshDashboard,
    runAction,
    importVm,
    reconcileInventory,
    syncHosts,
    syncGuests,
    decommissionHost,
    restoreHost,
    removeHostRecord,
    clearNotification: () => setNotification(null),
  };
}
