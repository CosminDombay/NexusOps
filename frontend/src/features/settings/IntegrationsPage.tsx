import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Plug, Plus, RefreshCw, TestTube2, Trash2, XCircle } from 'lucide-react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import {
  createIntegration,
  deleteIntegration,
  listIntegrations,
  testIntegration,
  updateIntegration,
} from './api/integrationsApi';
import type {
  Integration,
  IntegrationPayload,
  IntegrationTestResult,
  IntegrationType,
} from './types/integration';

type AuthMode = 'url_only' | 'username_password' | 'token' | 'username_token';
type IntegrationKind = 'proxmox' | 'prometheus' | 'grafana' | 'tailscale';

type FormState = {
  kind: IntegrationKind;
  name: string;
  type: IntegrationType;
  enabled: boolean;
  url: string;
  username: string;
  tokenId: string;
  authMode: AuthMode;
  verifySsl: boolean;
  timeoutSeconds: string;
  credentialRefs: Record<string, string>;
  advancedOpen: boolean;
  advancedJson: string;
};

const presets: Record<
  IntegrationKind,
  Omit<FormState, 'credentialRefs' | 'advancedOpen' | 'advancedJson'>
> = {
  proxmox: {
    kind: 'proxmox',
    name: 'Proxmox',
    type: 'infrastructure_provider',
    enabled: true,
    url: '',
    username: '',
    tokenId: '',
    authMode: 'username_token',
    verifySsl: false,
    timeoutSeconds: '15',
  },
  prometheus: {
    kind: 'prometheus',
    name: 'Prometheus',
    type: 'monitoring',
    enabled: true,
    url: '',
    username: '',
    tokenId: '',
    authMode: 'url_only',
    verifySsl: true,
    timeoutSeconds: '10',
  },
  grafana: {
    kind: 'grafana',
    name: 'Grafana',
    type: 'monitoring',
    enabled: true,
    url: '',
    username: '',
    tokenId: '',
    authMode: 'token',
    verifySsl: true,
    timeoutSeconds: '10',
  },
  tailscale: {
    kind: 'tailscale',
    name: 'Tailscale',
    type: 'networking',
    enabled: true,
    url: 'https://api.tailscale.com',
    username: '',
    tokenId: '',
    authMode: 'token',
    verifySsl: true,
    timeoutSeconds: '10',
  },
};

export function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [form, setForm] = useState<FormState>(() => formFromPreset('proxmox'));
  const [tests, setTests] = useState<Record<string, IntegrationTestResult>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [integrationLoadError, setIntegrationLoadError] = useState<string | null>(null);
  const [credentialLoadError, setCredentialLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingIntegrationId, setEditingIntegrationId] = useState<string | null>(null);

  const configPreview = useMemo(() => buildConfig(form), [form]);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setActionError(null);
    setIntegrationLoadError(null);
    setCredentialLoadError(null);

    const [integrationResult, credentialResult] = await Promise.allSettled([
      listIntegrations(),
      listCredentials(),
    ]);

    if (integrationResult.status === 'fulfilled') {
      setIntegrations(integrationResult.value);
    } else {
      setIntegrationLoadError(getApiErrorMessage(integrationResult.reason));
    }

    if (credentialResult.status === 'fulfilled') {
      setCredentials(credentialResult.value);
    } else {
      setCredentialLoadError(getApiErrorMessage(credentialResult.reason));
    }

    setIsLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function submit() {
    setActionError(null);
    try {
      const advancedConfig = form.advancedOpen ? JSON.parse(form.advancedJson || '{}') : {};
      const payload: IntegrationPayload = {
        name: form.name,
        type: form.type,
        enabled: form.enabled,
        config: { ...configPreview, ...advancedConfig },
        credential_refs: Object.fromEntries(
          Object.entries(form.credentialRefs).filter(([, value]) => value),
        ),
      };
      if (editingIntegrationId) {
        const updated = await updateIntegration(editingIntegrationId, payload);
        setIntegrations((current) =>
          current.map((integration) => (integration.id === updated.id ? updated : integration)),
        );
        closeDrawer();
      } else {
        const created = await createIntegration(payload);
        setIntegrations((current) => [created, ...current]);
        closeDrawer();
      }
    } catch (requestError) {
      setActionError(
        requestError instanceof SyntaxError
          ? 'Advanced configuration must be valid JSON.'
          : getApiErrorMessage(requestError),
      );
    }
  }

  async function toggle(integration: Integration) {
    try {
      const updated = await updateIntegration(integration.id, { enabled: !integration.enabled });
      setIntegrations((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (requestError) {
      setActionError(getApiErrorMessage(requestError));
    }
  }

  async function runTest(integration: Integration) {
    try {
      const result = await testIntegration(integration.id);
      setTests((current) => ({ ...current, [integration.id]: result }));
    } catch (requestError) {
      setActionError(getApiErrorMessage(requestError));
    }
  }

  async function remove(integration: Integration) {
    if (
      !window.confirm(
        `Delete integration ${integration.name}? Provider connections using it will fall back to environment configuration or become unavailable.`,
      )
    ) {
      return;
    }
    setActionError(null);
    try {
      await deleteIntegration(integration.id);
      setIntegrations((current) => current.filter((item) => item.id !== integration.id));
      setTests((current) => {
        const next = { ...current };
        delete next[integration.id];
        return next;
      });
    } catch (requestError) {
      setActionError(getApiErrorMessage(requestError));
    }
  }

  function choosePreset(kind: IntegrationKind) {
    setForm(formFromPreset(kind));
  }

  function openCreateDrawer() {
    setEditingIntegrationId(null);
    setForm(formFromPreset('proxmox'));
    setIsAddOpen(true);
  }

  function openEditDrawer(integration: Integration) {
    const kind = inferIntegrationKind(integration);
    const credentialRefs = integration.credential_refs ?? {};
    setEditingIntegrationId(integration.id);
    setForm({
      ...formFromPreset(kind),
      name: integration.name,
      type: integration.type,
      enabled: integration.enabled,
      url: String(
        integration.config.api_url ?? integration.config.url ?? integration.config.base_url ?? '',
      ),
      username: String(integration.config.token_id ?? integration.config.username ?? ''),
      tokenId: String(integration.config.token_id ?? ''),
      verifySsl: integration.config.verify_ssl !== false,
      timeoutSeconds: String(integration.config.timeout_seconds ?? presets[kind].timeoutSeconds),
      credentialRefs,
    });
    setIsAddOpen(true);
  }

  function closeDrawer() {
    setEditingIntegrationId(null);
    setIsAddOpen(false);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Integrations"
        description="Structured provider, monitoring, and networking configuration with credential-backed secrets."
      />

      {integrationLoadError ? (
        <p className="rounded-md border border-rose-400/30 bg-rose-950/50 px-3 py-2 text-sm text-rose-200">
          {integrationLoadError}
        </p>
      ) : null}
      {actionError ? (
        <p className="rounded-md border border-rose-400/30 bg-rose-950/50 px-3 py-2 text-sm text-rose-200">
          {actionError}
        </p>
      ) : null}

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">Configured Integrations</h3>
            <p className="mt-1 text-sm text-zinc-500">
              {integrationLoadError
                ? 'Unable to load integration records.'
                : `${integrations.length} integration records.`}
            </p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
            type="button"
            onClick={() => void refresh()}
          >
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
                <dl className="mt-4 space-y-2 text-sm">
                  <Info
                    label="URL"
                    value={String(
                      integration.config.api_url ??
                        integration.config.url ??
                        integration.config.base_url ??
                        'Not configured',
                    )}
                  />
                  <Info
                    label="SSL"
                    value={
                      integration.config.verify_ssl === false
                        ? 'Verification disabled'
                        : 'Verification enabled'
                    }
                  />
                  <Info
                    label="Timeout"
                    value={`${String(integration.config.timeout_seconds ?? 'default')}s`}
                  />
                </dl>
                {Object.keys(integration.credential_refs ?? {}).length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {Object.keys(integration.credential_refs).map((key) => (
                      <span
                        key={key}
                        className="rounded bg-zinc-100 px-2 py-1 font-mono text-xs text-zinc-700"
                      >
                        {key}: ********
                      </span>
                    ))}
                  </div>
                ) : null}
                {tests[integration.id] ? (
                  <p
                    className={`mt-3 rounded-md px-3 py-2 text-sm ${tests[integration.id].status === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}
                  >
                    {tests[integration.id].message}
                  </p>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                    type="button"
                    onClick={() => void toggle(integration)}
                  >
                    {integration.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md bg-cyan-400 px-3 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300"
                    type="button"
                    onClick={() => void runTest(integration)}
                  >
                    <TestTube2 className="h-4 w-4" aria-hidden="true" />
                    Test
                  </button>
                  <button
                    className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                    type="button"
                    onClick={() => openEditDrawer(integration)}
                  >
                    Edit
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md border border-rose-400/50 px-3 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-950/40"
                    type="button"
                    onClick={() => void remove(integration)}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    Delete
                  </button>
                </div>
              </article>
            ))}
            {!integrationLoadError && integrations.length === 0 ? (
              <p className="p-5 text-sm text-zinc-500">No integrations configured yet.</p>
            ) : null}
          </div>
        ) : null}
      </section>

      <div className="flex justify-end">
        <button
          className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50"
          type="button"
          onClick={openCreateDrawer}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add integration
        </button>
      </div>

      <ContextDrawer
        description="Secrets stay in credential references; plain config stores URLs, SSL, and timeout behavior."
        isOpen={isAddOpen}
        title={editingIntegrationId ? 'Edit Integration' : 'Add Integration'}
        width="xl"
        onClose={closeDrawer}
      >
        <div className="mt-4 flex flex-wrap gap-2">
          {(Object.keys(presets) as IntegrationKind[]).map((kind) => (
            <button
              key={kind}
              className={`rounded-md border px-3 py-2 text-sm font-semibold transition ${
                form.kind === kind
                  ? 'border-cyan-400 bg-cyan-400 text-zinc-950'
                  : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50'
              }`}
              type="button"
              onClick={() => choosePreset(kind)}
            >
              {presets[kind].name}
            </button>
          ))}
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          {credentialLoadError ? (
            <p className="rounded-md border border-amber-400/30 bg-amber-950/40 px-3 py-2 text-sm text-amber-100 lg:col-span-3">
              Credential references could not be loaded. You can still view integrations, but secret
              selectors may be incomplete.
            </p>
          ) : null}
          <TextInput
            label="Name"
            value={form.name}
            onChange={(name) => setForm({ ...form, name })}
          />
          <label className="text-sm font-medium text-zinc-700">
            Auth mode
            <select
              className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={form.authMode}
              onChange={(event) => setForm({ ...form, authMode: event.target.value as AuthMode })}
            >
              <option value="url_only">URL only</option>
              <option value="username_password">URL + username/password</option>
              <option value="token">URL + token</option>
              <option value="username_token">URL + username + token</option>
            </select>
          </label>
          <label className="flex items-center gap-2 pt-6 text-sm font-medium text-zinc-700">
            <input
              checked={form.enabled}
              type="checkbox"
              onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
            />
            Enabled
          </label>
          <TextInput label="URL" value={form.url} onChange={(url) => setForm({ ...form, url })} />
          {form.authMode === 'username_password' || form.authMode === 'username_token' ? (
            <TextInput
              label="Username / token ID"
              value={form.username || form.tokenId}
              onChange={(value) => setForm({ ...form, username: value, tokenId: value })}
            />
          ) : null}
          <CredentialSelect
            credentials={credentials}
            label={secretLabel(form.authMode)}
            value={form.credentialRefs[secretKey(form)] ?? ''}
            onChange={(value) =>
              setForm({
                ...form,
                credentialRefs: { ...form.credentialRefs, [secretKey(form)]: value },
              })
            }
          />
          <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
            <input
              checked={form.verifySsl}
              type="checkbox"
              onChange={(event) => setForm({ ...form, verifySsl: event.target.checked })}
            />
            Verify SSL
          </label>
          <TextInput
            label="Timeout seconds"
            value={form.timeoutSeconds}
            onChange={(timeoutSeconds) => setForm({ ...form, timeoutSeconds })}
          />
        </div>

        <details
          className="mt-4 rounded-md border border-zinc-200 p-3"
          open={form.advancedOpen}
          onToggle={(event) => setForm({ ...form, advancedOpen: event.currentTarget.open })}
        >
          <summary className="cursor-pointer text-sm font-semibold text-zinc-700">
            Advanced Configuration
          </summary>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <pre className="overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-50">
              {JSON.stringify(configPreview, null, 2)}
            </pre>
            <textarea
              className="min-h-40 rounded-md border border-zinc-300 p-3 font-mono text-xs"
              value={form.advancedJson}
              onChange={(event) => setForm({ ...form, advancedJson: event.target.value })}
            />
          </div>
        </details>

        <div className="mt-4 flex justify-end">
          <button
            className="rounded-md bg-cyan-400 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300"
            type="button"
            onClick={() => void submit()}
          >
            {editingIntegrationId ? 'Save Integration' : 'Add Integration'}
          </button>
        </div>
      </ContextDrawer>
    </div>
  );
}

function formFromPreset(kind: IntegrationKind): FormState {
  return { ...presets[kind], credentialRefs: {}, advancedOpen: false, advancedJson: '{}' };
}

function inferIntegrationKind(integration: Integration): IntegrationKind {
  const name = integration.name.toLowerCase();
  const url = String(
    integration.config.api_url ?? integration.config.url ?? integration.config.base_url ?? '',
  ).toLowerCase();
  if (name.includes('grafana') || url.includes('grafana')) return 'grafana';
  if (name.includes('prometheus') || url.includes('prometheus')) return 'prometheus';
  if (name.includes('tailscale') || url.includes('tailscale')) return 'tailscale';
  return 'proxmox';
}

function buildConfig(form: FormState): Record<string, unknown> {
  const timeout = Number(form.timeoutSeconds);
  const base = {
    verify_ssl: form.verifySsl,
    timeout_seconds: Number.isFinite(timeout) ? timeout : 10,
  };
  if (form.kind === 'proxmox') {
    return { ...base, api_url: form.url, token_id: form.tokenId || form.username };
  }
  if (form.kind === 'grafana') {
    return { ...base, base_url: form.url };
  }
  return { ...base, url: form.url };
}

function secretKey(form: FormState): string {
  if (form.kind === 'proxmox') return 'token_secret';
  if (form.authMode === 'username_password') return 'password';
  if (form.kind === 'prometheus') return 'bearer_token';
  return 'api_token';
}

function secretLabel(mode: AuthMode): string {
  if (mode === 'url_only') return 'Credential reference (optional)';
  if (mode === 'username_password') return 'Password credential';
  return 'Token credential';
}

function TextInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input
        className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function CredentialSelect({
  credentials,
  label,
  value,
  onChange,
}: {
  credentials: Credential[];
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <select
        className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">None</option>
        {credentials.map((credential) => (
          <option key={credential.id} value={credential.id}>
            {credential.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function Status({ enabled }: { enabled: boolean }) {
  const Icon = enabled ? CheckCircle2 : XCircle;
  const className = enabled
    ? 'text-emerald-700 bg-emerald-50 ring-emerald-200'
    : 'text-zinc-600 bg-zinc-100 ring-zinc-200';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${className}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {enabled ? 'Enabled' : 'Disabled'}
    </span>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="break-all text-right font-medium text-zinc-800">{value}</dd>
    </div>
  );
}

function formatType(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}
