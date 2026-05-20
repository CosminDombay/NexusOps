import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { useAuth } from '../../auth/hooks/useAuth';
import { getServer } from '../../inventory/api/serversApi';
import type { Server } from '../../inventory/types/server';
import { FileBrowserPanel } from '../components/FileBrowserPanel';
import { ShellPanel } from '../components/ShellPanel';

export function HostToolsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [server, setServer] = useState<Server | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!id) {
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        setServer(await getServer(id));
      } catch (loadError) {
        setError(getApiErrorMessage(loadError));
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [id]);

  const canUseRemoteAccess = user?.role === 'admin' || user?.role === 'operator' || user?.is_superuser;

  if (isLoading) {
    return <div className="h-80 animate-pulse rounded-lg bg-zinc-100" />;
  }

  if (!server || error) {
    return <div className="rounded-lg border border-amber-200 bg-amber-50 p-5 text-amber-900">{error ?? 'Host could not be loaded.'}</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader title={`${server.hostname} Tools`} description="Backend-mediated shell and file access for this inventory-managed host." />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link className="text-sm font-semibold text-zinc-600 hover:text-zinc-950" to={`/nodes/${server.id}`}>
          Back to node operations
        </Link>
        {!canUseRemoteAccess ? (
          <span className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">
            Remote access is restricted to operators and admins.
          </span>
        ) : null}
      </div>

      <div className="grid min-h-[calc(100vh-220px)] gap-5">
        <FileBrowserPanel server={server} canUseFiles={Boolean(canUseRemoteAccess)} />
        <ShellPanel server={server} canUseShell={Boolean(canUseRemoteAccess)} compact />
      </div>
    </div>
  );
}
