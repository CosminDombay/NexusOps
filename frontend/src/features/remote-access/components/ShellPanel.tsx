import { useEffect, useRef, useState } from 'react';
import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';
import { Cable, CircleStop } from 'lucide-react';

import type { Server } from '../../inventory/types/server';
import { buildShellWebSocketUrl, createShellToken } from '../api/remoteAccessApi';

type ConnectionState = 'idle' | 'connecting' | 'connected' | 'closed' | 'error';

export function ShellPanel({ server, canUseShell, compact = false }: { server: Server; canUseShell: boolean; compact?: boolean }) {
  const shellFrame = useRef<HTMLDivElement | null>(null);
  const terminalElement = useRef<HTMLDivElement | null>(null);
  const terminal = useRef<Terminal | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const fitAddon = useRef<FitAddon | null>(null);
  const dataSubscription = useRef<ReturnType<Terminal['onData']> | null>(null);
  const [status, setStatus] = useState<ConnectionState>('idle');

  useEffect(() => {
    if (!terminalElement.current || terminal.current) {
      return;
    }
    const term = new Terminal({
      cursorBlink: true,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      fontSize: 13,
      theme: { background: '#09090b', foreground: '#e4e4e7' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(terminalElement.current);
    fit.fit();
    term.writeln(`NexusOps remote shell: ${server.hostname}`);
    term.writeln('Connect when ready. Commands are not recorded by NexusOps.');
    terminal.current = term;
    fitAddon.current = fit;

    const onResize = () => fit.fit();
    const resizeObserver = new ResizeObserver(() => fit.fit());
    if (shellFrame.current) {
      resizeObserver.observe(shellFrame.current);
    }
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      resizeObserver.disconnect();
      dataSubscription.current?.dispose();
      socket.current?.close();
      term.dispose();
      terminal.current = null;
    };
  }, [server.hostname]);

  async function connect() {
    if (!canUseShell || status === 'connected' || status === 'connecting') {
      return;
    }
    setStatus('connecting');
    terminal.current?.writeln('\r\nConnecting...');
    let scopedToken: string;
    try {
      scopedToken = await createShellToken(server.id);
    } catch {
      setStatus('error');
      terminal.current?.writeln('\r\nUnable to create a scoped shell session token.');
      return;
    }
    const ws = new WebSocket(buildShellWebSocketUrl(server.id, scopedToken));
    socket.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      terminal.current?.writeln('\r\nConnected.\r\n');
    };
    ws.onmessage = (event) => terminal.current?.write(String(event.data));
    ws.onerror = () => {
      setStatus('error');
      terminal.current?.writeln('\r\nShell connection failed.');
    };
    ws.onclose = () => {
      setStatus((current) => (current === 'error' ? 'error' : 'closed'));
      terminal.current?.writeln('\r\nShell session closed.');
    };

    dataSubscription.current?.dispose();
    dataSubscription.current =
      terminal.current?.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(data);
        }
      }) ?? null;
  }

  function disconnect() {
    socket.current?.close();
    socket.current = null;
  }

  if (!canUseShell) {
    return (
      <div className="rounded-lg border border-zinc-200 bg-white p-5 text-sm text-zinc-600">
        Shell access requires an operator or admin role.
      </div>
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-zinc-950">Shell</h2>
          <p className="text-sm text-zinc-500">
            {server.hostname} - {server.ip_address}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-700">{status}</span>
          <button
            className="inline-flex items-center gap-2 rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-400"
            type="button"
            disabled={status === 'connected' || status === 'connecting'}
            onClick={() => void connect()}
          >
            <Cable className="h-4 w-4" aria-hidden="true" />
            Connect
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={disconnect}
          >
            <CircleStop className="h-4 w-4" aria-hidden="true" />
            Disconnect
          </button>
        </div>
      </div>
      <div
        ref={shellFrame}
        className={`${
          compact ? 'h-[300px] min-h-[220px]' : 'h-[520px] min-h-[280px]'
        } max-h-[calc(100vh-180px)] resize-y overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950 p-2 shadow-inner`}
      >
        <div ref={terminalElement} className="h-full" />
      </div>
    </section>
  );
}
