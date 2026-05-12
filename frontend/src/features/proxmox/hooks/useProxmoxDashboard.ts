import { useCallback, useEffect, useState } from 'react';

import { getApiErrorMessage } from '../../../lib/api/client';
import { getProxmoxDashboard, runVmAction } from '../api/proxmoxApi';
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

  return {
    dashboard,
    isLoading,
    error,
    actionByVmId,
    notification,
    refreshDashboard,
    runAction,
    clearNotification: () => setNotification(null),
  };
}
