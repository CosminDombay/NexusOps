import { useEffect, useMemo, useState } from 'react';
import { Clock3, History, Pencil, Play, Plus, Trash2 } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { ContextDrawer } from '../../../components/ContextDrawer';
import { PageHeader } from '../../../components/layout/PageHeader';
import { PageActionButton, RuntimeBadge, OperationalToolbar } from '../../../components/operations/OperationalComponents';
import { SearchField } from '../../../components/search/SearchField';
import { getApiErrorMessage } from '../../../lib/api/client';
import { matchesSearch } from '../../../lib/search/match';
import { listCredentials } from '../../credentials/api/credentialsApi';
import type { Credential } from '../../credentials/types/credential';
import { listServers } from '../../inventory/api/serversApi';
import { TargetSelector } from '../../inventory/components/TargetSelector';
import { useTargetSelection } from '../../inventory/hooks/useTargetSelection';
import type { Server } from '../../inventory/types/server';
import { listOperationalActions } from '../../jobs/api/jobsApi';
import type { OperationalAction } from '../../jobs/types/job';
import { listPackageDefinitions } from '../../packages/api/packagesApi';
import type { PackageDefinition } from '../../packages/types/package';
import { listProfiles } from '../../profiles/api/profilesApi';
import type { InfrastructureProfile } from '../../profiles/types/profile';
import {
  createAutomation,
  deleteAutomation,
  disableAutomation,
  enableAutomation,
  listAutomations,
  runAutomation,
  updateAutomation,
} from '../api/automationsApi';
import type { Automation, AutomationPayload } from '../types/automation';

type FormState = {
  name: string;
  schedule_type: 'interval' | 'cron';
  interval_seconds: string;
  cron_expression: string;
  target_server_ids: string[];
  operation_type: 'action' | 'profile' | 'package';
  reference_id: string;
  execution_credential_ref: string;
};

const initialForm: FormState = {
  name: 'Hourly uptime check',
  schedule_type: 'interval',
  interval_seconds: '3600',
  cron_expression: '0 2 * * *',
  target_server_ids: [],
  operation_type: 'action',
  reference_id: 'check-uptime',
  execution_credential_ref: '',
};

export function AutomationsPage() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [form, setForm] = useState<FormState>(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [editingAutomationId, setEditingAutomationId] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [search, setSearch] = useState('');
  const targetSelector = useTargetSelection('bulk');

  const operationOptions = useMemo(() => {
    if (form.operation_type === 'profile')
      return profiles.map((profile) => ({ value: profile.id, label: profile.name }));
    if (form.operation_type === 'package')
      return packages.map((pkg) => ({ value: pkg.id, label: pkg.name }));
    return actions.map((action) => ({ value: action.id, label: action.name }));
  }, [actions, form.operation_type, packages, profiles]);
  const filteredAutomations = useMemo(
    () =>
      automations.filter((automation) =>
        matchesSearch(search, [
          automation.name,
          automation.description,
          automation.schedule_type,
          automation.cron_expression,
          automation.interval_seconds,
          automation.operation_type,
          automation.reference_id,
          automation.target_server_ids,
          automation.runtime_state,
          automation.last_status,
          automation.recent_executions,
        ]),
      ),
    [automations, search],
  );

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextAutomations, nextServers, nextActions, nextProfiles, nextPackages, nextCredentials] =
        await Promise.all([
          listAutomations(),
          listServers(),
          listOperationalActions(),
          listProfiles(),
          listPackageDefinitions(),
          listCredentials(),
        ]);
      setAutomations(nextAutomations);
      setServers(nextServers);
      setActions(nextActions);
      setProfiles(nextProfiles);
      setPackages(nextPackages);
      setCredentials(nextCredentials);
      setForm((current) => ({
        ...current,
        target_server_ids: current.target_server_ids.length
          ? current.target_server_ids
          : nextServers[0]
            ? [nextServers[0].id]
            : [],
        reference_id: current.reference_id || nextActions[0]?.id || '',
      }));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSave() {
    const payload = toPayload(form);
    if (!payload) {
      setError('Automation needs a name, target host, schedule, and operation reference.');
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      if (editingAutomationId) {
        const updated = await updateAutomation(editingAutomationId, payload);
        setAutomations((current) =>
          current.map((automation) => (automation.id === updated.id ? updated : automation)),
        );
        setSuccess(`Updated automation ${updated.name}.`);
        resetForm();
      } else {
        const created = await createAutomation(payload);
        setAutomations((current) => [created, ...current]);
        setSuccess(`Created automation ${created.name}.`);
        setIsFormOpen(false);
      }
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  function startEdit(automation: Automation) {
    setIsFormOpen(true);
    setEditingAutomationId(automation.id);
    setForm({
      name: automation.name,
      schedule_type: automation.schedule_type,
      interval_seconds: String(automation.interval_seconds ?? 3600),
      cron_expression: automation.cron_expression ?? '0 2 * * *',
      target_server_ids: automation.target_server_ids,
      operation_type:
        automation.operation_type === 'profile' || automation.operation_type === 'package'
          ? automation.operation_type
          : 'action',
      reference_id: automation.reference_id ?? '',
      execution_credential_ref: automation.execution_credential_ref ?? '',
    });
    targetSelector.setMode(automation.target_server_ids.length > 1 ? 'bulk' : 'single');
    targetSelector.setSelectedId(automation.target_server_ids[0] ?? '');
    targetSelector.setSelectedIds(automation.target_server_ids);
    setError(null);
    setSuccess(null);
  }

  function resetForm() {
    setEditingAutomationId(null);
    setIsFormOpen(false);
    setForm({
      ...initialForm,
      target_server_ids: servers[0] ? [servers[0].id] : [],
      reference_id: actions[0]?.id ?? '',
      execution_credential_ref: '',
    });
    targetSelector.setMode('bulk');
    targetSelector.setSelectedId(servers[0]?.id ?? '');
    targetSelector.setSelectedIds(servers[0] ? [servers[0].id] : []);
  }

  async function handleDelete(automation: Automation) {
    const confirmed = window.confirm(
      `Delete automation ${automation.name}? Scheduled runs will stop, but existing workflow/job history remains.`,
    );
    if (!confirmed) {
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      await deleteAutomation(automation.id);
      setAutomations((current) => current.filter((item) => item.id !== automation.id));
      if (editingAutomationId === automation.id) {
        resetForm();
      }
      setSuccess(`Deleted automation ${automation.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function toggle(automation: Automation) {
    setIsWorking(true);
    try {
      const updated = automation.enabled
        ? await disableAutomation(automation.id)
        : await enableAutomation(automation.id);
      setAutomations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function runNow(automation: Automation) {
    setIsWorking(true);
    setError(null);
    try {
      const workflow = await runAutomation(automation.id);
      setSuccess(`Queued workflow ${workflow.id}.`);
      await refresh();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Automations"
        description="Recurring operational checks and package/profile compliance runs backed by persistent workflows."
        actions={
          <PageActionButton icon={Plus} onClick={() => setIsFormOpen(true)}>
            Create automation
          </PageActionButton>
        }
      />
      {error ? (
        <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>
      ) : null}
      {success ? (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p>
      ) : null}

      <ContextDrawer
        description="Schedule actions, packages, or profiles while preserving the automation list context."
        isOpen={isFormOpen}
        title={editingAutomationId ? 'Edit Automation' : 'Create Automation'}
        width="xl"
        onClose={resetForm}
      >
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <TextInput
            label="Name"
            value={form.name}
            onChange={(value) => setForm({ ...form, name: value })}
          />
          <label className="text-sm font-medium text-zinc-700">
            Schedule
            <select
              className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={form.schedule_type}
              onChange={(event) =>
                setForm({
                  ...form,
                  schedule_type: event.target.value as FormState['schedule_type'],
                })
              }
            >
              <option value="interval">Interval</option>
              <option value="cron">Cron</option>
            </select>
          </label>
          {form.schedule_type === 'interval' ? (
            <TextInput
              label="Every seconds"
              value={form.interval_seconds}
              onChange={(value) => setForm({ ...form, interval_seconds: value })}
            />
          ) : (
            <TextInput
              label="Cron expression"
              value={form.cron_expression}
              onChange={(value) => setForm({ ...form, cron_expression: value })}
            />
          )}
          <label className="text-sm font-medium text-zinc-700">
            Operation
            <select
              className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={form.operation_type}
              onChange={(event) => {
                const operationType = event.target.value as FormState['operation_type'];
                setForm({ ...form, operation_type: operationType, reference_id: '' });
              }}
            >
              <option value="action">Predefined action</option>
              <option value="package">Package</option>
              <option value="profile">Profile</option>
            </select>
          </label>
          <label className="text-sm font-medium text-zinc-700">
            Reference
            <select
              className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={form.reference_id}
              onChange={(event) => setForm({ ...form, reference_id: event.target.value })}
            >
              <option value="">Select operation</option>
              {operationOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-zinc-700">
            Execution / sudo credential
            <select
              className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={form.execution_credential_ref}
              onChange={(event) => setForm({ ...form, execution_credential_ref: event.target.value })}
            >
              <option value="">Use target saved credential or passwordless access</option>
              {credentials
                .filter((credential) => credential.credential_type === 'password' || credential.credential_type === 'ssh_password')
                .map((credential) => (
                  <option key={credential.id} value={credential.id}>
                    {credential.name} ({credential.credential_type.replace('_', ' ')})
                  </option>
                ))}
            </select>
          </label>
          <div className="lg:col-span-3">
            <TargetSelector
              servers={servers}
              selection={{ ...targetSelector.selection, selectedIds: form.target_server_ids }}
              filters={targetSelector.filters}
              title="Automation targets"
              description="Schedule actions, packages, or profiles against consistent inventory host selections."
              onFiltersChange={targetSelector.setFilters}
              onSelectionChange={(selection) => {
                targetSelector.setMode(selection.mode);
                targetSelector.setSelectedId(selection.selectedId);
                targetSelector.setSelectedIds(selection.selectedIds);
                setForm({
                  ...form,
                  target_server_ids:
                    selection.mode === 'bulk'
                      ? selection.selectedIds
                      : selection.selectedId
                        ? [selection.selectedId]
                        : [],
                });
              }}
            />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <PageActionButton disabled={isWorking} onClick={() => void handleSave()}>
            {editingAutomationId ? 'Save automation' : 'Create automation'}
          </PageActionButton>
        </div>
      </ContextDrawer>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Scheduled automations</h3>
          <p className="mt-1 text-sm text-zinc-500">{automations.length} configured.</p>
          <SearchField
            className="mt-3"
            placeholder="Search automations, schedules, operations..."
            value={search}
            onChange={setSearch}
          />
        </div>
        {isLoading ? <div className="m-5 h-24 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <div className="divide-y divide-zinc-100">
            {filteredAutomations.map((automation) => (
              <article key={automation.id} className="grid gap-4 p-5 xl:grid-cols-[minmax(0,1fr)_auto]">
                <div className="space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="font-semibold text-zinc-950">{automation.name}</h4>
                        <RuntimeBadge value={automation.runtime_state} />
                        <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">
                          {automation.enabled ? 'enabled' : 'disabled'}
                        </span>
                        {automation.execution_credential_ref ? (
                          <span className="rounded-full bg-sky-50 px-2 py-1 text-xs font-semibold text-sky-700 ring-1 ring-inset ring-sky-200">
                            execution credential
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 text-sm text-zinc-500">
                        {automation.schedule_type === 'interval'
                          ? `Every ${automation.interval_seconds}s`
                          : automation.cron_expression}{' '}
                        - {automation.operation_type} {automation.reference_id}
                      </p>
                    </div>
                    <div className="grid gap-2 text-xs text-zinc-500 sm:grid-cols-3">
                      <RuntimeFact label="Last run" value={formatDate(automation.last_run_at)} />
                      <RuntimeFact label="Next run" value={formatDate(automation.next_run_at)} />
                      <RuntimeFact label="Executions" value={String(automation.execution_count)} />
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase text-zinc-500">Targets</p>
                    <AutomationTargets automation={automation} servers={servers} />
                  </div>

                  <div className="grid gap-3 lg:grid-cols-3">
                    <RuntimeMetric icon={Clock3} label="Last duration" value={formatDurationSeconds(automation.last_duration_seconds)} />
                    <RuntimeMetric icon={History} label="Last success" value={formatDate(automation.last_success_at)} />
                    <RuntimeMetric icon={History} label="Last failure" value={formatDate(automation.last_failure_at)} />
                  </div>

                  <RecentExecutions automation={automation} />
                </div>
                <OperationalToolbar>
                  <button
                    className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700"
                    disabled={isWorking}
                    type="button"
                    onClick={() => void toggle(automation)}
                  >
                    {automation.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700"
                    disabled={isWorking}
                    type="button"
                    onClick={() => startEdit(automation)}
                  >
                    <Pencil className="h-4 w-4" aria-hidden="true" />
                    Edit
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md bg-zinc-950 px-3 py-2 text-sm font-semibold text-white disabled:bg-zinc-300"
                    disabled={isWorking}
                    type="button"
                    onClick={() => void runNow(automation)}
                  >
                    <Play className="h-4 w-4" aria-hidden="true" />
                    Run now
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700"
                    disabled={isWorking}
                    type="button"
                    onClick={() => void handleDelete(automation)}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    Delete
                  </button>
                </OperationalToolbar>
              </article>
            ))}
            {filteredAutomations.length === 0 ? (
              <p className="p-5 text-sm text-zinc-500">
                {search ? 'No automations match this search.' : 'No scheduled automations yet.'}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
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

function AutomationTargets({ automation, servers }: { automation: Automation; servers: Server[] }) {
  const targets = automation.target_nodes.length
    ? automation.target_nodes
    : automation.target_server_ids.map((serverId) => {
        const server = servers.find((candidate) => candidate.id === serverId);
        return {
          id: serverId,
          hostname: server?.hostname ?? serverId,
          node_type: server?.node_type ?? 'unknown',
          environment: server?.environment ?? 'unknown',
          provider: server?.provider ?? 'unknown',
          source: server?.source ?? 'unknown',
          tags: server?.tags ?? [],
        };
      });

  if (!targets.length) {
    return <p className="text-sm text-zinc-500">No targets selected.</p>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {targets.map((target) => (
        <div key={target.id} className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-zinc-950">{target.hostname}</span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-zinc-700 ring-1 ring-inset ring-zinc-200">
              {formatNodeType(target.node_type)}
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            {target.environment} - {target.provider} - {target.source}
          </p>
          {target.tags.length ? (
            <p className="mt-1 text-xs text-zinc-500">{target.tags.slice(0, 3).join(', ')}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function RecentExecutions({ automation }: { automation: Automation }) {
  if (!automation.recent_executions.length) {
    return <p className="text-sm text-zinc-500">No execution history yet.</p>;
  }

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase text-zinc-500">Recent execution history</p>
      <div className="grid gap-2">
        {automation.recent_executions.map((execution) => (
          <div key={execution.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-200 px-3 py-2 text-sm">
            <div>
              <span className="font-semibold text-zinc-950">{formatLabel(execution.workflow_type)}</span>
              <span className="ml-2 text-zinc-500">{execution.target_nodes.join(', ') || execution.target_hostname || 'Unknown target'}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <RuntimeBadge value={execution.status} />
              <span className="text-xs text-zinc-500">{formatDurationSeconds(execution.duration_seconds)}</span>
              <span className="text-xs text-zinc-500">{formatDate(execution.started_at ?? execution.created_at)}</span>
            </div>
            {execution.error_message ? <p className="basis-full text-xs text-rose-700">{execution.error_message}</p> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function RuntimeFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-28 rounded-md bg-zinc-50 px-3 py-2">
      <div className="font-semibold uppercase">{label}</div>
      <div className="mt-1 text-zinc-800">{value}</div>
    </div>
  );
}

function RuntimeMetric({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="rounded-md border border-zinc-200 px-3 py-2">
      <Icon className="h-4 w-4 text-zinc-500" aria-hidden="true" />
      <div className="mt-2 text-xs font-semibold uppercase text-zinc-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Never';
}

function formatDurationSeconds(value: number | null): string {
  if (value == null) return 'Not measured';
  if (value < 60) return `${value}s`;
  return `${Math.floor(value / 60)}m ${value % 60}s`;
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNodeType(value: string): string {
  if (value === 'lxc') return 'LXC';
  if (value === 'vm') return 'VM';
  return formatLabel(value);
}

function toPayload(form: FormState): AutomationPayload | null {
  if (!form.name.trim() || !form.reference_id || form.target_server_ids.length === 0) return null;
  return {
    name: form.name.trim(),
    enabled: true,
    schedule_type: form.schedule_type,
    interval_seconds: form.schedule_type === 'interval' ? Number(form.interval_seconds) : null,
    cron_expression: form.schedule_type === 'cron' ? form.cron_expression.trim() : null,
    target_mode: form.target_server_ids.length > 1 ? 'multiple_hosts' : 'single_host',
    target_server_ids: form.target_server_ids,
    operation_type: form.operation_type,
    reference_id: form.reference_id,
    variables_json: {},
    credential_refs: {},
    execution_credential_ref: form.execution_credential_ref || null,
  };
}
