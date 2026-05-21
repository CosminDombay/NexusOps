import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { getApiErrorMessage } from '../../../lib/api/client';
import { runVmAction } from '../../proxmox/api/proxmoxApi';
import type { ProxmoxVmAction } from '../../proxmox/types/proxmox';
import {
  archiveServer,
  checkServersHealthBulk,
  createServer,
  decommissionServer,
  deleteServer,
  listServers,
  restoreServer,
  unmanageServer,
  updateServer,
} from '../api/serversApi';
import type { CreateServerPayload, Server, UpdateServerPayload } from '../types/server';

type UseServersResult = {
  servers: Server[];
  isLoading: boolean;
  isCreating: boolean;
  error: string | null;
  createError: string | null;
  mutationError: string | null;
  isCheckingHealth: boolean;
  isRunningVmLifecycleAction: boolean;
  includeInactive: boolean;
  setIncludeInactive: (value: boolean) => void;
  refreshServers: () => Promise<void>;
  addServer: (payload: CreateServerPayload) => Promise<boolean>;
  editServer: (serverId: string, payload: UpdateServerPayload) => Promise<boolean>;
  removeServer: (serverId: string) => Promise<boolean>;
  archiveInventoryServer: (serverId: string) => Promise<boolean>;
  decommissionInventoryServer: (serverId: string) => Promise<boolean>;
  restoreInventoryServer: (serverId: string) => Promise<boolean>;
  unmanageInventoryServer: (serverId: string) => Promise<boolean>;
  refreshHealth: (serverIds?: string[]) => Promise<boolean>;
  runVmLifecycleAction: (serverIds: string[], action: ProxmoxVmAction) => Promise<boolean>;
  clearCreateError: () => void;
  clearMutationError: () => void;
};

export function useServers(): UseServersResult {
  const [servers, setServers] = useState<Server[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [isRunningVmLifecycleAction, setIsRunningVmLifecycleAction] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);
  const hasLoadedRef = useRef(false);

  const refreshServers = useCallback(async () => {
    setIsLoading(!hasLoadedRef.current);
    setError(null);

    try {
      const nextServers = await listServers(includeInactive);
      setServers((currentServers) => reconcileServers(currentServers, nextServers));
      hasLoadedRef.current = true;
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, [includeInactive]);

  const addServer = useCallback(async (payload: CreateServerPayload) => {
    setIsCreating(true);
    setCreateError(null);

    try {
      const createdServer = await createServer(payload);
      setServers((currentServers) => [createdServer, ...currentServers]);
      return true;
    } catch (caughtError) {
      setCreateError(getApiErrorMessage(caughtError));
      return false;
    } finally {
      setIsCreating(false);
    }
  }, []);

  const editServer = useCallback(async (serverId: string, payload: UpdateServerPayload) => {
    setMutationError(null);

    try {
      const updatedServer = await updateServer(serverId, payload);
      setServers((currentServers) =>
        currentServers.map((server) => (server.id === serverId ? updatedServer : server)),
      );
      return true;
    } catch (caughtError) {
      setMutationError(getApiErrorMessage(caughtError));
      return false;
    }
  }, []);

  const removeServer = useCallback(async (serverId: string) => {
    setMutationError(null);

    try {
      await deleteServer(serverId);
      setServers((currentServers) => currentServers.filter((server) => server.id !== serverId));
      return true;
    } catch (caughtError) {
      setMutationError(getApiErrorMessage(caughtError));
      return false;
    }
  }, []);

  const archiveInventoryServer = useCallback(async (serverId: string) => {
    setMutationError(null);

    try {
      const archivedServer = await archiveServer(serverId);
      setServers((currentServers) =>
        currentServers.filter((server) => server.id !== serverId).concat(archivedServer),
      );
      await refreshServers();
      return true;
    } catch (caughtError) {
      setMutationError(getApiErrorMessage(caughtError));
      return false;
    }
  }, [refreshServers]);

  const decommissionInventoryServer = useCallback(async (serverId: string) => {
    setMutationError(null);
    try {
      await decommissionServer(serverId);
      await refreshServers();
      return true;
    } catch (caughtError) {
      setMutationError(getApiErrorMessage(caughtError));
      return false;
    }
  }, [refreshServers]);

  const restoreInventoryServer = useCallback(async (serverId: string) => {
    setMutationError(null);
    try {
      await restoreServer(serverId);
      await refreshServers();
      return true;
    } catch (caughtError) {
      setMutationError(getApiErrorMessage(caughtError));
      return false;
    }
  }, [refreshServers]);

  const unmanageInventoryServer = useCallback(async (serverId: string) => {
    setMutationError(null);
    try {
      await unmanageServer(serverId);
      await refreshServers();
      return true;
    } catch (caughtError) {
      setMutationError(getApiErrorMessage(caughtError));
      return false;
    }
  }, [refreshServers]);

  const refreshHealth = useCallback(async (serverIds?: string[]) => {
    setIsCheckingHealth(true);
    setMutationError(null);
    try {
      await checkServersHealthBulk(serverIds);
      await refreshServers();
      return true;
    } catch (caughtError) {
      setMutationError(getApiErrorMessage(caughtError));
      return false;
    } finally {
      setIsCheckingHealth(false);
    }
  }, [refreshServers]);

  const runVmLifecycleAction = useCallback(async (serverIds: string[], action: ProxmoxVmAction) => {
    setIsRunningVmLifecycleAction(true);
    setMutationError(null);

    const selectedServers = servers.filter((server) => serverIds.includes(server.id));
    const invalidServers = selectedServers.filter((server) => getInventoryVmId(server) === null);
    const lifecycleTargets = selectedServers
      .map((server) => ({ server, vmId: getInventoryVmId(server) }))
      .filter((target): target is { server: Server; vmId: number } => target.vmId !== null);

    if (lifecycleTargets.length === 0) {
      setMutationError('Select at least one Proxmox-backed inventory host with a VMID.');
      setIsRunningVmLifecycleAction(false);
      return false;
    }

    if (invalidServers.length > 0) {
      const invalidNames = invalidServers.map((server) => server.hostname).join(', ');
      setMutationError(`Lifecycle actions need Proxmox VMIDs. Update or unselect: ${invalidNames}.`);
      setIsRunningVmLifecycleAction(false);
      return false;
    }

    try {
      const results = await Promise.allSettled(lifecycleTargets.map((target) => runVmAction(target.vmId, action)));
      const failedResults = results.filter((result): result is PromiseRejectedResult => result.status === 'rejected');

      await refreshServers();

      if (failedResults.length > 0) {
        const firstError = getApiErrorMessage(failedResults[0].reason);
        setMutationError(
          `${lifecycleTargets.length - failedResults.length} ${action} request(s) succeeded, ${failedResults.length} failed. ${firstError}`,
        );
        return false;
      }

      return true;
    } catch (caughtError) {
      setMutationError(getApiErrorMessage(caughtError));
      return false;
    } finally {
      setIsRunningVmLifecycleAction(false);
    }
  }, [refreshServers, servers]);

  useEffect(() => {
    void refreshServers();
  }, [refreshServers]);

  return useMemo(
    () => ({
      servers,
      isLoading,
      isCreating,
      error,
      createError,
      mutationError,
      isCheckingHealth,
      isRunningVmLifecycleAction,
      includeInactive,
      setIncludeInactive,
      refreshServers,
      addServer,
      editServer,
      removeServer,
      archiveInventoryServer,
      decommissionInventoryServer,
      restoreInventoryServer,
      unmanageInventoryServer,
      refreshHealth,
      runVmLifecycleAction,
      clearCreateError: () => setCreateError(null),
      clearMutationError: () => setMutationError(null),
    }),
    [
      addServer,
      archiveInventoryServer,
      createError,
      decommissionInventoryServer,
      editServer,
      error,
      includeInactive,
      isCreating,
      isCheckingHealth,
      isLoading,
      isRunningVmLifecycleAction,
      mutationError,
      refreshServers,
      removeServer,
      restoreInventoryServer,
      refreshHealth,
      runVmLifecycleAction,
      servers,
      unmanageInventoryServer,
    ],
  );
}

function getInventoryVmId(server: Server): number | null {
  if (server.provider?.toLowerCase() !== 'proxmox') {
    return null;
  }

  const rawVmId = server.vmid ?? server.external_id;
  if (rawVmId === null || rawVmId === undefined || rawVmId === '') {
    return null;
  }

  const vmId = Number(rawVmId);
  return Number.isInteger(vmId) && vmId > 0 ? vmId : null;
}

function reconcileServers(currentServers: Server[], nextServers: Server[]): Server[] {
  if (currentServers.length === 0) {
    return nextServers;
  }
  const currentById = new Map(currentServers.map((server) => [server.id, server]));
  return nextServers.map((nextServer) => {
    const currentServer = currentById.get(nextServer.id);
    if (!currentServer) {
      return nextServer;
    }
    if (
      currentServer.updated_at === nextServer.updated_at &&
      currentServer.runtime_state?.last_checked_at === nextServer.runtime_state?.last_checked_at &&
      currentServer.runtime_state?.stale_after === nextServer.runtime_state?.stale_after
    ) {
      return currentServer;
    }
    return nextServer;
  });
}
