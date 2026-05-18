import { useCallback, useEffect, useState } from 'react';
import { ChevronRight, File, Folder, RefreshCw, Save, Undo2 } from 'lucide-react';

import { getApiErrorMessage } from '../../../lib/api/client';
import type { Server } from '../../inventory/types/server';
import { listRemoteFiles, readRemoteFile, writeRemoteFile } from '../api/remoteAccessApi';
import type { RemoteDirectoryListing, RemoteFileRead } from '../types/remoteAccess';
import { breadcrumbs, formatRemoteBytes, parentPath } from '../utils/path';

export function FileBrowserPanel({ server, canUseFiles }: { server: Server; canUseFiles: boolean }) {
  const [path, setPath] = useState('/');
  const [pathInput, setPathInput] = useState('/');
  const [listing, setListing] = useState<RemoteDirectoryListing | null>(null);
  const [openedFile, setOpenedFile] = useState<RemoteFileRead | null>(null);
  const [content, setContent] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDirectory = useCallback(
    async (nextPath: string) => {
      if (!canUseFiles) {
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const result = await listRemoteFiles(server.id, nextPath);
        setListing(result);
        setPath(result.path);
        setPathInput(result.path);
        setOpenedFile(null);
        setContent('');
      } catch (loadError) {
        setError(getApiErrorMessage(loadError));
      } finally {
        setIsLoading(false);
      }
    },
    [canUseFiles, server.id],
  );

  useEffect(() => {
    void loadDirectory('/');
  }, [loadDirectory]);

  async function openFile(filePath: string) {
    setIsLoading(true);
    setError(null);
    try {
      const result = await readRemoteFile(server.id, filePath);
      setOpenedFile(result);
      setContent(result.content);
    } catch (readError) {
      setError(getApiErrorMessage(readError));
    } finally {
      setIsLoading(false);
    }
  }

  async function saveFile() {
    if (!openedFile) {
      return;
    }
    const confirmed = window.confirm(`Save changes to ${openedFile.path}?`);
    if (!confirmed) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const result = await writeRemoteFile(server.id, {
        path: openedFile.path,
        content,
        expected_hash: openedFile.sha256,
      });
      setOpenedFile({ ...openedFile, content, sha256: result.sha256, size: result.size, modified_at: result.modified_at });
    } catch (saveError) {
      setError(getApiErrorMessage(saveError));
    } finally {
      setIsSaving(false);
    }
  }

  if (!canUseFiles) {
    return (
      <div className="rounded-lg border border-zinc-200 bg-white p-5 text-sm text-zinc-600">
        Remote files require an operator or admin role.
      </div>
    );
  }

  const dirty = openedFile ? content !== openedFile.content : false;

  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
      <div className="rounded-lg border border-zinc-200 bg-white">
        <div className="border-b border-zinc-200 p-4">
          <h2 className="text-lg font-semibold text-zinc-950">Files</h2>
          <p className="text-sm text-zinc-500">
            {server.hostname} - {server.ip_address}
          </p>
          <form
            className="mt-4 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void loadDirectory(pathInput);
            }}
          >
            <input
              className="min-w-0 flex-1 rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm"
              value={pathInput}
              onChange={(event) => setPathInput(event.target.value)}
            />
            <button className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white" type="submit">
              Go
            </button>
          </form>
          <div className="mt-3 flex flex-wrap items-center gap-1 text-xs text-zinc-500">
            {breadcrumbs(path).map((item, index) => (
              <button
                key={item.path}
                className="inline-flex items-center gap-1 rounded px-1.5 py-1 font-mono hover:bg-zinc-100"
                type="button"
                onClick={() => void loadDirectory(item.path)}
              >
                {index > 0 ? <ChevronRight className="h-3 w-3" aria-hidden="true" /> : null}
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-2">
          <button
            className="inline-flex items-center gap-2 rounded-md px-2 py-1 text-sm font-semibold text-zinc-700 hover:bg-zinc-100"
            type="button"
            onClick={() => void loadDirectory(parentPath(path))}
          >
            <Undo2 className="h-4 w-4" aria-hidden="true" />
            Up
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-md px-2 py-1 text-sm font-semibold text-zinc-700 hover:bg-zinc-100"
            type="button"
            onClick={() => void loadDirectory(path)}
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
            Refresh
          </button>
        </div>

        {error ? <div className="m-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{error}</div> : null}

        <div className="max-h-[420px] overflow-auto">
          {(listing?.entries ?? []).map((entry) => (
            <button
              key={entry.path}
              className="grid w-full grid-cols-[24px_minmax(0,1fr)_80px] items-center gap-2 border-b border-zinc-100 px-4 py-3 text-left text-sm hover:bg-zinc-50"
              type="button"
              onClick={() => {
                if (entry.type === 'directory') {
                  void loadDirectory(entry.path);
                } else if (entry.type === 'file') {
                  void openFile(entry.path);
                }
              }}
            >
              {entry.type === 'directory' ? <Folder className="h-4 w-4 text-sky-600" /> : <File className="h-4 w-4 text-zinc-500" />}
              <span className="min-w-0">
                <span className="block truncate font-mono font-semibold text-zinc-800">{entry.name}</span>
                <span className="block truncate text-xs text-zinc-500">{entry.permissions}</span>
              </span>
              <span className="text-right text-xs text-zinc-500">{entry.type === 'file' ? formatRemoteBytes(entry.size) : entry.type}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 p-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">{openedFile?.path ?? 'No file selected'}</h3>
            {openedFile ? (
              <p className="font-mono text-xs text-zinc-500">
                sha256:{openedFile.sha256} - {formatRemoteBytes(openedFile.size)}
              </p>
            ) : null}
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-400"
            type="button"
            disabled={!openedFile || !dirty || isSaving}
            onClick={() => void saveFile()}
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            {isSaving ? 'Saving' : 'Save'}
          </button>
        </div>
        <textarea
          className="h-[460px] w-full resize-y border-0 bg-zinc-950 p-4 font-mono text-sm leading-6 text-zinc-100 outline-none placeholder:text-zinc-500"
          disabled={!openedFile}
          value={openedFile ? content : ''}
          onChange={(event) => setContent(event.target.value)}
          placeholder="Select a file to view or edit."
          spellCheck={false}
        />
      </div>
    </section>
  );
}
