import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Plug, RefreshCw, TestTube2, XCircle } from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { createIntegration, listIntegrations, testIntegration, updateIntegration } from './api/integrationsApi';
import type { Integration, IntegrationPayload, IntegrationTestResult, IntegrationType } from './types/integration';

const defaults: IntegrationPayload[] = [
  { name: 'Proxmox', type: 'infrastructure_provider', enabled: true, config: { api_url: '' } },
  { name: 'Prometheus', type: 'monitoring', enabled: true, config: { url: '' } },
  { name: 'Grafana', type: 'monitoring', enabled: true, config: { base_url: '' } },
];

export function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [form, setForm] = useState<IntegrationPayload>(defaults[0]);
  const [configText, setConfigText] = useState(JSON.stringify(defaults[0].config, null, 2));
  const [tests, setTests] = useState<Record<string, IntegrationTestResult>>({});
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setIntegrations(await listIntegrations());
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function submit() {
    setError(null);
    try {
      const created = await createIntegration({ ...form, config: JSON.parse(configText) as Record<string, unknown> });
      setIntegrations((current) => [...current, created]);
    } catch (requestError) {
      setError(requestError instanceof SyntaxError ? 'Config must be valid JSON.' : getApiErrorMessage(requestError));
    }
  }

  async function toggle(integration: Integration) {
    try {
      const updated = await updateIntegration(integration.id, { enabled: !integration.enabled });
      setIntegrations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    }
  }

  async function runTest(integration: Integration) {
    try {
      const result = await testIntegration(integration.id);
      setTests((current) => ({ ...current, [integration.id]: result }));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Integrations" description="Central configuration for infrastructure providers, monitoring, networking, and database integrations." />

      {error ? <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">Configured Integrations</h3>
            <p className="mt-1 text-sm text-zinc-500">{integrations.length} integration records.</p>
          </div>
          <button className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={() => void refresh()}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        </div>
        {isLoading ? <div className="m-5 h-24 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <div className="grid gap-4 p-4 lg:grid-cols-3">
            {integrations.map((integration) => (
              <article key={integration.id} className="rounded-lg border border-zinc-200 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Plug className="h-4 w-4 text-zinc-500" aria-hidden="true" />
                      <h4 className="font-semibold text-zinc-950">{integration.name}</h4>
                    </div>
                    <p className="mt-1 text-sm text-zinc-500">{formatType(integration.type)}</p>
                  </div>
                  <Status enabled={integration.enabled} />
                </div>
                <pre className="mt-4 max-h-28 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-50">{JSON.stringify(integration.config, null, 2)}</pre>
                {tests[integration.id] ? (
                  <p className={`mt-3 rounded-md px-3 py-2 text-sm ${tests[integration.id].status === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                    {tests[integration.id].message}
                  </p>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={() => void toggle(integration)}>
                    {integration.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button className="inline-flex items-center gap-2 rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800" type="button" onClick={() => void runTest(integration)}>
                    <TestTube2 className="h-4 w-4" aria-hidden="true" />
                    Test
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Add Integration</h3>
        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_220px_160px]">
          <label className="text-sm font-medium text-zinc-700">
            Name
            <input className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </label>
          <label className="text-sm font-medium text-zinc-700">
            Type
            <select className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2" value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value as IntegrationType })}>
              <option value="infrastructure_provider">Infrastructure Provider</option>
              <option value="monitoring">Monitoring</option>
              <option value="networking">Networking</option>
              <option value="database">Database</option>
            </select>
          </label>
          <label className="flex items-center gap-2 pt-6 text-sm font-medium text-zinc-700">
            <input checked={form.enabled} type="checkbox" onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />
            Enabled
          </label>
        </div>
        <label className="mt-4 block text-sm font-medium text-zinc-700">
          Config JSON
          <textarea className="mt-1 min-h-36 w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm" value={configText} onChange={(event) => setConfigText(event.target.value)} />
        </label>
        <div className="mt-4 flex flex-wrap gap-2">
          {defaults.map((preset) => (
            <button key={preset.name} className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={() => {
              setForm(preset);
              setConfigText(JSON.stringify(preset.config, null, 2));
            }}>
              {preset.name}
            </button>
          ))}
          <button className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800" type="button" onClick={() => void submit()}>
            Add Integration
          </button>
        </div>
      </section>
    </div>
  );
}

function Status({ enabled }: { enabled: boolean }) {
  const Icon = enabled ? CheckCircle2 : XCircle;
  const className = enabled ? 'text-emerald-700 bg-emerald-50 ring-emerald-200' : 'text-zinc-600 bg-zinc-100 ring-zinc-200';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {enabled ? 'Enabled' : 'Disabled'}
    </span>
  );
}

function formatType(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}
