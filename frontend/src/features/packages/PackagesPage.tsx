import { useEffect, useState } from 'react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton } from '../../components/operations/OperationalComponents';
import {
  ExecutionVariablesModal,
  type ExecutionVariableValues,
} from '../../components/ExecutionVariablesModal';
import { VariableDefinitionEditor } from '../../components/VariableDefinitionEditor';
import { getApiErrorMessage } from '../../lib/api/client';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server } from '../inventory/types/server';
import {
  createPackageDefinition,
  clonePackageDefinition,
  deletePackageDefinition,
  executePackageDefinition,
  executePackageDefinitionBulk,
  listPackageDefinitions,
  resetPackageDefinition,
  updatePackageDefinition,
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
  uninstall_command: '',
  validation_command: '',
  variables: [],
  tags: [],
  tags_text: '',
  description: '',
};

export function PackagesPage() {
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [executingPackageId, setExecutingPackageId] = useState<string | null>(null);
  const [pendingPackage, setPendingPackage] = useState<PackageDefinition | null>(null);
  const [bulkResult, setBulkResult] = useState<BulkExecutionResponse | null>(null);
  const [editingPackageId, setEditingPackageId] = useState<string | null>(null);
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const targetSelector = useTargetSelection('single');

  useEffect(() => {
    async function loadPackages() {
      setIsLoading(true);
      setError(null);

      try {
        const [nextPackages, nextServers, nextCredentials] = await Promise.all([
          listPackageDefinitions(),
          listServers(),
          listCredentials(),
        ]);
        setPackages(nextPackages);
        setServers(nextServers);
        setCredentials(nextCredentials);
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

  function startEdit(packageDefinition: PackageDefinition) {
    setIsBuilderOpen(true);
    setEditingPackageId(packageDefinition.id);
    setFormState({
      id: packageDefinition.id,
      name: packageDefinition.name,
      category: packageDefinition.category,
      supported_os: packageDefinition.supported_os,
      supported_os_text: packageDefinition.supported_os.join(','),
      install_command: packageDefinition.install_command,
      uninstall_command: packageDefinition.uninstall_command,
      validation_command: packageDefinition.validation_command,
      variables: packageDefinition.variables,
      tags: packageDefinition.tags,
      tags_text: packageDefinition.tags.join(','),
      description: packageDefinition.description,
    });
    setError(null);
    setSuccess(null);
  }

  function resetEditor() {
    setEditingPackageId(null);
    setFormState(initialFormState);
    setIsBuilderOpen(false);
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
      const payload = {
        name: formState.name.trim(),
        category: formState.category.trim() || 'Custom',
        supported_os: splitCsv(formState.supported_os_text),
        install_command: formState.install_command.trim(),
        uninstall_command: formState.uninstall_command.trim(),
        validation_command: formState.validation_command.trim() || 'true',
        variables: formState.variables
          .filter((variable) => variable.name.trim())
          .map((variable) => ({
            ...variable,
            name: variable.name.trim(),
            description: variable.description.trim(),
          })),
        tags: splitCsv(formState.tags_text),
        description: formState.description.trim() || 'Custom package definition.',
      };
      if (editingPackageId) {
        const updated = await updatePackageDefinition(editingPackageId, payload);
        setPackages((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        setSuccess(`Updated package ${updated.name}.`);
      } else {
        const created = await createPackageDefinition({ id: formState.id.trim(), ...payload });
        setPackages((current) => [...current, created]);
        setSuccess(`Created package ${created.name}.`);
      }
      resetEditor();
    } catch (caughtError) {
      setError(
        caughtError instanceof SyntaxError
          ? 'Variables must be valid JSON.'
          : getApiErrorMessage(caughtError),
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function handleClonePackage(packageDefinition: PackageDefinition) {
    const id = window.prompt('Clone package as ID', `${packageDefinition.id}-copy`);
    if (!id) {
      return;
    }
    try {
      const cloned = await clonePackageDefinition(packageDefinition.id, {
        id: id.trim(),
        name: `${packageDefinition.name} Copy`,
      });
      setPackages((current) => [...current, cloned]);
      setSuccess(`Cloned package ${cloned.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleResetPackage(packageDefinition: PackageDefinition) {
    const confirmed = window.confirm(
      `Restore ${packageDefinition.name} to the built-in default? Current edits will be discarded.`,
    );
    if (!confirmed) {
      return;
    }
    try {
      const restored = await resetPackageDefinition(packageDefinition.id);
      setPackages((current) => current.map((item) => (item.id === restored.id ? restored : item)));
      setSuccess(`Restored package ${restored.name} to default.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleDeletePackage(packageId: string) {
    const confirmed = window.confirm(`Delete package definition ${packageId}?`);
    if (!confirmed) {
      return;
    }

    try {
      await deletePackageDefinition(packageId);
      setPackages((current) =>
        current.filter((packageDefinition) => packageDefinition.id !== packageId),
      );
      setSuccess(`Deleted package ${packageId}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  function handleExecutePackage(packageDefinition: PackageDefinition) {
    if (!selectedServerId && selectedServerIds.length === 0) {
      setError('Select one or more target hosts before running a package.');
      return;
    }
    setPendingPackage(packageDefinition);
    setError(null);
    setSuccess(null);
  }

  async function runPackage(
    packageDefinition: PackageDefinition,
    executionVariables: ExecutionVariableValues,
  ) {
    setExecutingPackageId(packageDefinition.id);
    setError(null);
    setSuccess(null);
    setBulkResult(null);

    try {
      if (selectedServerIds.length > 0) {
        const result = await executePackageDefinitionBulk(
          packageDefinition.id,
          selectedServerIds,
          executionVariables.variables,
          executionVariables.credential_refs,
        );
        setBulkResult(result);
        setSuccess(
          `Package ${packageDefinition.name}: ${result.success_count} succeeded, ${result.failure_count} failed.`,
        );
      } else {
        const job = await executePackageDefinition(
          packageDefinition.id,
          selectedServerId,
          executionVariables.variables,
          executionVariables.credential_refs,
        );
        setSuccess(`Started package ${packageDefinition.name}. Job status: ${job.status}.`);
      }
      setPendingPackage(null);
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
        actions={
          <PageActionButton tone="secondary" onClick={() => setIsBuilderOpen(true)}>
            Create package
          </PageActionButton>
        }
      />

      <TargetSelector
        servers={servers}
        selection={{
          mode: targetSelector.selection.mode,
          selectedId: selectedServerId,
          selectedIds: selectedServerIds,
        }}
        filters={targetSelector.filters}
        title="Package targets"
        description="Install package definitions against one host or a filtered bulk selection."
        onFiltersChange={targetSelector.setFilters}
        onSelectionChange={(selection) => {
          targetSelector.setMode(selection.mode);
          setSelectedServerId(selection.selectedId);
          setSelectedServerIds(selection.selectedIds);
        }}
      />

      <ContextDrawer
        description="Create or tune package standards without losing the target and package list context."
        isOpen={isBuilderOpen}
        title={editingPackageId ? 'Edit Package' : 'Create Package'}
        width="xl"
        onClose={resetEditor}
      >
        <PackageBuilder
          formState={formState}
          editingPackageId={editingPackageId}
          isCreating={isCreating}
          onCreate={handleCreatePackage}
          onCancel={resetEditor}
          onFieldChange={updateField}
          onVariablesChange={(variables) => setFormState((current) => ({ ...current, variables }))}
        />
      </ContextDrawer>

      {success ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {success}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error}
        </p>
      ) : null}
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
              onClone={handleClonePackage}
              onEdit={startEdit}
              onExecute={handleExecutePackage}
              onReset={handleResetPackage}
            />
          ))}
        </div>
      ) : null}
      <ExecutionVariablesModal
        credentials={credentials}
        isLoading={executingPackageId === pendingPackage?.id}
        isOpen={pendingPackage !== null}
        previewItems={
          pendingPackage
            ? [`Install ${pendingPackage.name}`, `Validate ${pendingPackage.name}`]
            : []
        }
        targetLabel={`${selectedServerIds.length || 1} host(s) selected`}
        title={pendingPackage ? `Run ${pendingPackage.name}` : 'Run package'}
        variables={pendingPackage?.variables ?? []}
        onCancel={() => setPendingPackage(null)}
        onConfirm={(values) => (pendingPackage ? runPackage(pendingPackage, values) : undefined)}
      />
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
            <span
              className={
                item.success ? 'font-semibold text-emerald-700' : 'font-semibold text-rose-700'
              }
            >
              {item.success ? 'Success' : 'Failed'}
            </span>
            <span className="ml-2 text-zinc-700">
              {item.target_hostname ?? item.target_server_id}
            </span>
            {item.error ? (
              <p className="mt-1 font-mono text-xs text-zinc-500">{item.error}</p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function PackageBuilder({
  formState,
  editingPackageId,
  isCreating,
  onCreate,
  onCancel,
  onFieldChange,
  onVariablesChange,
}: {
  formState: FormState;
  editingPackageId: string | null;
  isCreating: boolean;
  onCreate: () => void;
  onCancel: () => void;
  onFieldChange: (name: keyof FormState, value: string) => void;
  onVariablesChange: (variables: FormState['variables']) => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">
        {editingPackageId ? 'Edit package definition' : 'Add package definition'}
      </h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TextInput
          label="ID"
          name="id"
          placeholder="custom-agent"
          value={formState.id}
          onChange={onFieldChange}
        />
        <TextInput
          label="Name"
          name="name"
          placeholder="Custom Agent"
          value={formState.name}
          onChange={onFieldChange}
        />
        <TextInput
          label="Category"
          name="category"
          placeholder="Monitoring"
          value={formState.category}
          onChange={onFieldChange}
        />
        <TextInput
          label="Supported OS"
          name="supported_os_text"
          placeholder="ubuntu,debian"
          value={formState.supported_os_text}
          onChange={onFieldChange}
        />
        <TextInput
          label="Tags"
          name="tags_text"
          placeholder="monitoring,agent"
          value={formState.tags_text}
          onChange={onFieldChange}
        />
        <TextInput
          label="Description"
          name="description"
          placeholder="Installs a custom agent"
          value={formState.description}
          onChange={onFieldChange}
        />
        <TextArea
          label="Install command"
          name="install_command"
          value={formState.install_command}
          onChange={onFieldChange}
        />
        <TextArea
          label="Uninstall command"
          name="uninstall_command"
          value={formState.uninstall_command}
          onChange={onFieldChange}
        />
        <TextArea
          label="Validation command"
          name="validation_command"
          value={formState.validation_command}
          onChange={onFieldChange}
        />
        <VariableDefinitionEditor variables={formState.variables} onChange={onVariablesChange} />
      </div>
      <div className="mt-4 flex justify-end gap-2">
        {editingPackageId ? (
          <button
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
            type="button"
            onClick={onCancel}
          >
            Cancel
          </button>
        ) : null}
        <button
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
          disabled={isCreating}
          type="button"
          onClick={onCreate}
        >
          {isCreating ? 'Saving' : editingPackageId ? 'Save package' : 'Create package'}
        </button>
      </div>
    </section>
  );
}

function PackageCard({
  packageDefinition,
  isExecuting,
  onDelete,
  onClone,
  onEdit,
  onExecute,
  onReset,
}: {
  packageDefinition: PackageDefinition;
  isExecuting: boolean;
  onDelete: (packageId: string) => void;
  onClone: (packageDefinition: PackageDefinition) => void;
  onEdit: (packageDefinition: PackageDefinition) => void;
  onExecute: (packageDefinition: PackageDefinition) => void;
  onReset: (packageDefinition: PackageDefinition) => void;
}) {
  return (
    <article className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm ring-1 ring-transparent transition hover:border-zinc-300 hover:shadow-md">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-zinc-950">{packageDefinition.name}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">
            {packageDefinition.description}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex w-fit rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
            {packageDefinition.category}
          </span>
          <span className="inline-flex w-fit rounded-full bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-600 ring-1 ring-inset ring-zinc-200">
            {packageDefinition.is_builtin ? 'Built-in' : 'Custom'}
          </span>
          {packageDefinition.is_modified ? <Badge label="Modified" /> : null}
          {packageDefinition.source_template_id && !packageDefinition.is_builtin ? (
            <Badge label="Cloned" />
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {packageDefinition.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-zinc-50 px-2.5 py-1 text-xs text-zinc-600 ring-1 ring-zinc-200"
          >
            {tag}
          </span>
        ))}
      </div>

      <dl className="mt-5 space-y-4 rounded-md border border-zinc-200 bg-zinc-50 p-3">
        <CommandBlock label="Install" value={packageDefinition.install_command} />
        {packageDefinition.uninstall_command ? (
          <CommandBlock label="Uninstall" value={packageDefinition.uninstall_command} />
        ) : null}
        <CommandBlock label="Validate" value={packageDefinition.validation_command} />
      </dl>
      {packageDefinition.variables.length ? (
        <div className="mt-4 rounded-md border border-zinc-200 bg-white p-3">
          <p className="text-xs font-semibold uppercase text-zinc-500">Variables</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {packageDefinition.variables.map((variable) => (
              <span
                key={variable.name}
                className="rounded bg-zinc-100 px-2 py-1 font-mono text-xs text-zinc-700"
              >
                {variable.name}
                {variable.required ? ' *' : ''}
                {variable.sensitive ? ' sensitive' : ''}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <p className="mt-4 text-xs text-zinc-500">
        Supported OS: {packageDefinition.supported_os.join(', ')}
      </p>

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={() => onClone(packageDefinition)}
        >
          Clone
        </button>
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={() => onEdit(packageDefinition)}
        >
          Edit
        </button>
        {packageDefinition.is_builtin && packageDefinition.is_modified ? (
          <button
            className="rounded-md border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-700 transition hover:bg-amber-50"
            type="button"
            onClick={() => onReset(packageDefinition)}
          >
            Restore default
          </button>
        ) : null}
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

function Badge({ label }: { label: string }) {
  return (
    <span className="inline-flex w-fit rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
      {label}
    </span>
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
