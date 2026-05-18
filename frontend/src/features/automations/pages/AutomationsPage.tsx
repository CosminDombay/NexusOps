import { useEffect, useMemo, useState } from 'react';
import { Play } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
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
import { createAutomation, disableAutomation, enableAutomation, listAutomations, runAutomation } from '../api/automationsApi';
import type { Automation, AutomationPayload } from '../types/automation';

type FormState = {
  name: string;
  schedule_type: 'interval' | 'cron';
  interval_seconds: string;
  cron_expression: string;
  target_server_ids: string[];
  operation_type: 'action' | 'profile' | 'package';
  reference_id: string;
};

const initialForm: FormState = {
  name: 'Hourly uptime check',
  schedule_type: 'interval',
  interval_seconds: '3600',
  cron_expression: '0 2 * * *',
  target_server_ids: [],
  operation_type: 'action',
  reference_id: 'check-uptime',
};

export function AutomationsPage() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [form, setForm] = useState<FormState>(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const targetSelector = useTargetSelection('bulk');

  const operationOptions = useMemo(() => {
    if (form.operation_type === 'profile') return profiles.map((profile) => ({ value: profile.id, label: profile.name }));
    if (form.operation_type === 'package') return packages.map((pkg) => ({ value: pkg.id, label: pkg.name }));
    return actions.map((action) => ({ value: action.id, label: action.name }));
  }, [actions, form.operation_type, packages, profiles]);

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextAutomations, nextServers, nextActions, nextProfiles, nextPackages] = await Promise.all([
        listAutomations(),
        listServers(),
        listOperationalActions(),
        listProfiles(),
        listPackageDefinitions(),
      ]);
      setAutomations(nextAutomations);
      setServers(nextServers);
      setActions(nextActions);
      setProfiles(nextProfiles);
      setPackages(nextPackages);
      setForm((current) => ({
        ...current,
        target_server_ids: current.target_server_ids.length ? current.target_server_ids : nextServers[0] ? [nextServers[0].id] : [],
        reference_id: current.reference_id || nextActions[0]?.id || '',
      }));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreate() {
    const payload = toPayload(form);
    if (!payload) {
      setError('Automation needs a name, target host, schedule, and operation reference.');
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await createAutomation(payload);
      setAutomations((current) => [created, ...current]);
      setSuccess(`Created automation ${created.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function toggle(automation: Automation) {
    setIsWorking(true);
    try {
      const updated = automation.enabled ? await disableAutomation(automation.id) : await enableAutomation(automation.id);
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
      <PageHeader title="Automations" description="Recurring operational checks and package/profile compliance runs backed by persistent workflows." />
      {error ? <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
      {success ? <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p> : null}

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Create automation</h3>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <TextInput label="Name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} />
          <label className="text-sm font-medium text-zinc-700">
            Schedule
            <select className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={form.schedule_type} onChange={(event) => setForm({ ...form, schedule_type: event.target.value as FormState['schedule_type'] })}>
              <option value="interval">Interval</option>
              <option value="cron">Cron</option>
            </select>
          </label>
          {form.schedule_type === 'interval' ? (
            <TextInput label="Every seconds" value={form.interval_seconds} onChange={(value) => setForm({ ...form, interval_seconds: value })} />
          ) : (
            <TextInput label="Cron expression" value={form.cron_expression} onChange={(value) => setForm({ ...form, cron_expression: value })} />
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
            <select className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={form.reference_id} onChange={(event) => setForm({ ...form, reference_id: event.target.value })}>
              <option value="">Select operation</option>
              {operationOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
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
                  target_server_ids: selection.mode === 'bulk' ? selection.selectedIds : selection.selectedId ? [selection.selectedId] : [],
                });
              }}
            />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <button className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-zinc-300" disabled={isWorking} type="button" onClick={() => void handleCreate()}>
            Create automation
          </button>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Scheduled automations</h3>
          <p className="mt-1 text-sm text-zinc-500">{automations.length} configured.</p>
        </div>
        {isLoading ? <div className="m-5 h-24 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <div className="divide-y divide-zinc-100">
            {automations.map((automation) => (
              <article key={automation.id} className="flex flex-col gap-3 p-5 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="font-semibold text-zinc-950">{automation.name}</h4>
                    <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">{automation.enabled ? 'enabled' : 'disabled'}</span>
                    {automation.last_status ? <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">last {automation.last_status}</span> : null}
                  </div>
                  <p className="mt-1 text-sm text-zinc-500">
                    {automation.schedule_type === 'interval' ? `Every ${automation.interval_seconds}s` : automation.cron_expression} - {automation.operation_type} {automation.reference_id}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700" disabled={isWorking} type="button" onClick={() => void toggle(automation)}>
                    {automation.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button className="inline-flex items-center gap-2 rounded-md bg-zinc-950 px-3 py-2 text-sm font-semibold text-white disabled:bg-zinc-300" disabled={isWorking} type="button" onClick={() => void runNow(automation)}>
                    <Play className="h-4 w-4" aria-hidden="true" />
                    Run now
                  </button>
                </div>
              </article>
            ))}
            {automations.length === 0 ? <p className="p-5 text-sm text-zinc-500">No scheduled automations yet.</p> : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
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
  };
}
