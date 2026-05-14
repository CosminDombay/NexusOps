import { useEffect, useState } from 'react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listServers } from '../inventory/api/serversApi';
import type { Server } from '../inventory/types/server';
import {
  createPackageDefinition,
  deletePackageDefinition,
  executePackageDefinition,
  executePackageDefinitionBulk,
  listPackageDefinitions,
} from './api/packagesApi';
import type { CreatePackageDefinitionPayload, PackageDefinition } from './types/package';
import type { BulkExecutionResponse } from '../jobs/types/job';

type FormState = CreatePackageDefinitionPayload & {
  supported_os_text: string;
  tags_text: string;
};

const initialFormState: FormState = {
  id: '',
  name: '',
  category: '',
  supported_os: [],
  supported_os_text: 'ubuntu,debian',
  install_command: '',
  validation_command: '',
  tags: [],
  tags_text: '',
  description: '',
};

export function PackagesPage() {
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [executingPackageId, setExecutingPackageId] = useState<string | null>(null);
  const [bulkResult, setBulkResult] = useState<BulkExecutionResponse | null>(null);

  useEffect(() => {
    async function loadPackages() {
      setIsLoading(true);
      setError(null);

      try {
        const [nextPackages, nextServers] = await Promise.all([listPackageDefinitions(), listServers()]);
        setPackages(nextPackages);
        setServers(nextServers);
        setSelectedServerId((current) => current || nextServers[0]?.id || '');
      } catch (caughtError) {
        setError(getApiErrorMessage(caughtError));
      } finally {
        setIsLoading(false);
      }
    }

    void loadPackages();
  }, []);

  function updateField(name: keyof FormState, value: string) {
    setFormState((current) => ({ ...current, [name]: value }));
    setError(null);
    setSuccess(null);
  }

  async function handleCreatePackage() {
    if (!formState.id.trim() || !formState.name.trim() || !formState.install_command.trim()) {
      setError('Package id, name, and install command are required.');
      return;
    }

    setIsCreating(true);
    setError(null);
    setSuccess(null);

    try {
      const created = await createPackageDefinition({
        id: formState.id.trim(),
        name: formState.name.trim(),
        category: formState.category.trim() || 'Custom',
        supported_os: splitCsv(formState.supported_os_text),
        install_command: formState.install_command.trim(),
        validation_command: formState.validation_command.trim() || 'true',
        tags: splitCsv(formState.tags_text),
        description: formState.description.trim() || 'Custom package definition.',
      });
      setPackages((current) => [...current, created]);
      setFormState(initialFormState);
      setSuccess(`Created package ${created.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDeletePackage(packageId: string) {
    const confirmed = window.confirm(`Delete package definition ${packageId}?`);
    if (!confirmed) {
      return;
    }

    try {
      await deletePackageDefinition(packageId);
      setPackages((current) => current.filter((packageDefinition) => packageDefinition.id !== packageId));
      setSuccess(`Deleted package ${packageId}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleExecutePackage(packageDefinition: PackageDefinition) {
    if (!selectedServerId && selectedServerIds.length === 0) {
      setError('Select one or more target hosts before running a package.');
      return;
    }

    const targetCount = selectedServerIds.length || 1;
    const confirmed = window.confirm(`Run ${packageDefinition.name} on ${targetCount} host(s)?`);
    if (!confirmed) {
      return;
    }

      setExecutingPackageId(packageDefinition.id);
      setError(null);
      setSuccess(null);
      setBulkResult(null);

    try {
      if (selectedServerIds.length > 0) {
        const result = await executePackageDefinitionBulk(packageDefinition.id, selectedServerIds);
        setBulkResult(result);
        setSuccess(`Package ${packageDefinition.name}: ${result.success_count} succeeded, ${result.failure_count} failed.`);
      } else {
        const job = await executePackageDefinition(packageDefinition.id, selectedServerId);
        setSuccess(`Started package ${packageDefinition.name}. Job status: ${job.status}.`);
      }
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setExecutingPackageId(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Package Definitions"
        description="Reusable package standards that profiles can compose into orchestration workflows."
      />

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Single target</span>
            <select
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              value={selectedServerId}
              onChange={(event) => setSelectedServerId(event.target.value)}
            >
              <option value="">Select inventory host</option>
              {servers.map((server) => (
                <option key={server.id} value={server.id}>
                  {server.hostname} ({server.ip_address})
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Bulk targets</span>
            <select
              className="mt-2 min-h-28 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
              multiple
              value={selectedServerIds}
              onChange={(event) =>
                setSelectedServerIds(Array.from(event.target.selectedOptions, (option) => option.value))
              }
            >
              {servers.map((server) => (
                <option key={server.id} value={server.id}>
                  {server.hostname} ({server.ip_address})
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-zinc-500">
              Bulk selection takes precedence over the single target.
            </p>
          </label>
        </div>
      </section>

      <PackageBuilder
        formState={formState}
        isCreating={isCreating}
        onCreate={handleCreatePackage}
        onFieldChange={updateField}
      />

      {success ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">{success}</p> : null}
      {error ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</p> : null}
      {bulkResult ? <BulkResultPanel result={bulkResult} /> : null}
      {isLoading ? <LoadingGrid /> : null}
      {!isLoading && !error ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {packages.map((packageDefinition) => (
            <PackageCard
              key={packageDefinition.id}
              isExecuting={executingPackageId === packageDefinition.id}
              packageDefinition={packageDefinition}
              onDelete={handleDeletePackage}
              onExecute={handleExecutePackage}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function BulkResultPanel({ result }: { result: BulkExecutionResponse }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">Bulk package result</h3>
      <p className="mt-1 text-sm text-zinc-500">
        {result.success_count} succeeded, {result.failure_count} failed
      </p>
      <div className="mt-4 divide-y divide-zinc-100 rounded-md border border-zinc-200">
        {result.results.map((item) => (
          <div key={item.target_server_id} className="px-3 py-2 text-sm">
            <span className={item.success ? 'font-semibold text-emerald-700' : 'font-semibold text-rose-700'}>
              {item.success ? 'Success' : 'Failed'}
            </span>
            <span className="ml-2 text-zinc-700">{item.target_hostname ?? item.target_server_id}</span>
            {item.error ? <p className="mt-1 font-mono text-xs text-zinc-500">{item.error}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function PackageBuilder({
  formState,
  isCreating,
  onCreate,
  onFieldChange,
}: {
  formState: FormState;
  isCreating: boolean;
  onCreate: () => void;
  onFieldChange: (name: keyof FormState, value: string) => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">Add package definition</h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TextInput label="ID" name="id" placeholder="custom-agent" value={formState.id} onChange={onFieldChange} />
        <TextInput label="Name" name="name" placeholder="Custom Agent" value={formState.name} onChange={onFieldChange} />
        <TextInput label="Category" name="category" placeholder="Monitoring" value={formState.category} onChange={onFieldChange} />
        <TextInput label="Supported OS" name="supported_os_text" placeholder="ubuntu,debian" value={formState.supported_os_text} onChange={onFieldChange} />
        <TextInput label="Tags" name="tags_text" placeholder="monitoring,agent" value={formState.tags_text} onChange={onFieldChange} />
        <TextInput label="Description" name="description" placeholder="Installs a custom agent" value={formState.description} onChange={onFieldChange} />
        <TextArea label="Install command" name="install_command" value={formState.install_command} onChange={onFieldChange} />
        <TextArea label="Validation command" name="validation_command" value={formState.validation_command} onChange={onFieldChange} />
      </div>
      <div className="mt-4 flex justify-end">
        <button
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
          disabled={isCreating}
          type="button"
          onClick={onCreate}
        >
          {isCreating ? 'Creating' : 'Create package'}
        </button>
      </div>
    </section>
  );
}

function PackageCard({
  packageDefinition,
  isExecuting,
  onDelete,
  onExecute,
}: {
  packageDefinition: PackageDefinition;
  isExecuting: boolean;
  onDelete: (packageId: string) => void;
  onExecute: (packageDefinition: PackageDefinition) => void;
}) {
  return (
    <article className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">{packageDefinition.name}</h3>
          <p className="mt-1 text-sm text-zinc-500">{packageDefinition.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex w-fit rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
            {packageDefinition.category}
          </span>
          <span className="inline-flex w-fit rounded-full bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-600 ring-1 ring-inset ring-zinc-200">
            {packageDefinition.is_builtin ? 'Built-in' : 'Custom'}
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {packageDefinition.tags.map((tag) => (
          <span key={tag} className="rounded-full bg-zinc-50 px-2.5 py-1 text-xs text-zinc-600 ring-1 ring-zinc-200">
            {tag}
          </span>
        ))}
      </div>

      <dl className="mt-5 space-y-4">
        <CommandBlock label="Install" value={packageDefinition.install_command} />
        <CommandBlock label="Validate" value={packageDefinition.validation_command} />
      </dl>

      <p className="mt-4 text-xs text-zinc-500">
        Supported OS: {packageDefinition.supported_os.join(', ')}
      </p>

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        {!packageDefinition.is_builtin ? (
          <button
            className="rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-50"
            type="button"
            onClick={() => onDelete(packageDefinition.id)}
          >
            Delete
          </button>
        ) : null}
        <button
          className="rounded-md bg-zinc-950 px-3 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
          disabled={isExecuting}
          type="button"
          onClick={() => onExecute(packageDefinition)}
        >
          {isExecuting ? 'Running' : 'Run package'}
        </button>
      </div>
    </article>
  );
}

function TextInput({
  label,
  name,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  name: keyof FormState;
  value: string;
  placeholder: string;
  onChange: (name: keyof FormState, value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input
        className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </label>
  );
}

function TextArea({
  label,
  name,
  value,
  onChange,
}: {
  label: string;
  name: keyof FormState;
  value: string;
  onChange: (name: keyof FormState, value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700 xl:col-span-3">
      {label}
      <textarea
        className="mt-1 min-h-24 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 font-mono text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
        value={value}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </label>
  );
}

function CommandBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-normal text-zinc-500">{label}</dt>
      <dd className="mt-1 overflow-auto rounded-md bg-zinc-950 p-3 font-mono text-xs leading-5 text-zinc-50">
        {value}
      </dd>
    </div>
  );
}

function splitCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function LoadingGrid() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-64 animate-pulse rounded-lg bg-zinc-100" />
      ))}
    </div>
  );
}
