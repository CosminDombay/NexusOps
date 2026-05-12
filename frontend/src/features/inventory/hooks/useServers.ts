import { useCallback, useEffect, useMemo, useState } from 'react';

import { getApiErrorMessage } from '../../../lib/api/client';
import { createServer, listServers } from '../api/serversApi';
import type { CreateServerPayload, Server } from '../types/server';

type UseServersResult = {
  servers: Server[];
  isLoading: boolean;
  isCreating: boolean;
  error: string | null;
  createError: string | null;
  refreshServers: () => Promise<void>;
  addServer: (payload: CreateServerPayload) => Promise<boolean>;
  clearCreateError: () => void;
};

export function useServers(): UseServersResult {
  const [servers, setServers] = useState<Server[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

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
      refreshServers,
      addServer,
      clearCreateError: () => setCreateError(null),
    }),
    [addServer, createError, error, isCreating, isLoading, refreshServers, servers],
  );
}
