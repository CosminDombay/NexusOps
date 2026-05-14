import { useCallback, useEffect, useMemo, useState } from 'react';

import { getApiErrorMessage } from '../../../lib/api/client';
import { archiveServer, checkServersHealthBulk, createServer, deleteServer, listServers, updateServer } from '../api/serversApi';
import type { CreateServerPayload, Server, UpdateServerPayload } from '../types/server';

type UseServersResult = {
  servers: Server[];
  isLoading: boolean;
  isCreating: boolean;
  error: string | null;
  createError: string | null;
  mutationError: string | null;
  isCheckingHealth: boolean;
  refreshServers: () => Promise<void>;
  addServer: (payload: CreateServerPayload) => Promise<boolean>;
  editServer: (serverId: string, payload: UpdateServerPayload) => Promise<boolean>;
  removeServer: (serverId: string) => Promise<boolean>;
  archiveInventoryServer: (serverId: string) => Promise<boolean>;
  refreshHealth: (serverIds?: string[]) => Promise<boolean>;
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

  const refreshServers = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const nextServers = await listServers();
      setServers(nextServers);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, []);

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
      refreshServers,
      addServer,
      editServer,
      removeServer,
      archiveInventoryServer,
      refreshHealth,
      clearCreateError: () => setCreateError(null),
      clearMutationError: () => setMutationError(null),
    }),
    [
      addServer,
      archiveInventoryServer,
      createError,
      editServer,
      error,
      isCreating,
      isCheckingHealth,
      isLoading,
      mutationError,
      refreshServers,
      removeServer,
      refreshHealth,
      servers,
    ],
  );
}
