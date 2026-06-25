import { useCallback, useEffect, useMemo, useState } from 'react';
import type { DragEvent } from 'react';
import { ArrowDown, ArrowUp, Package, Play, Plus, ShieldCheck, Trash2, UsersRound, Terminal } from 'lucide-react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton } from '../../components/operations/OperationalComponents';
import { SearchField } from '../../components/search/SearchField';
import {
  ExecutionVariablesModal,
  type ExecutionVariableValues,
} from '../../components/ExecutionVariablesModal';
import { VariableDefinitionEditor } from '../../components/VariableDefinitionEditor';
import { getApiErrorMessage } from '../../lib/api/client';
import { matchesSearch } from '../../lib/search/match';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listDeployments } from '../deployments/api/deploymentsApi';
import type { Deployment } from '../deployments/types/deployment';
import { listLinuxGroups, listLinuxUsers, listPermissionTemplates } from '../identity/api/identityApi';
import type { LinuxGroup, LinuxUser, PermissionTemplate } from '../identity/types/identity';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server } from '../inventory/types/server';
import { listOperationalActions } from '../jobs/api/jobsApi';
import { JobStatusBadge } from '../jobs/components/JobStatusBadge';
import type { OperationalAction } from '../jobs/types/job';
import { listPackageDefinitions } from '../packages/api/packagesApi';
import type { PackageDefinition } from '../packages/types/package';
import {
  applyProfile,
  applyProfileBulk,
  cloneProfile,
  createProfile,
  deleteProfile,
  listProfiles,
  resetProfile,
  updateProfile,
} from './api/profilesApi';
import type {
  ApplyProfileBulkResult,
  ApplyProfileResult,
  CreateInfrastructureProfilePayload,
  InfrastructureProfile,
  ProfileStep,
} from './types/profile';

type ProfileFormState = Omit<CreateInfrastructureProfilePayload, 'tags' | 'steps' | 'variables'> & {
  tags_text: string;
  steps: ProfileStep[];
  variables: CreateInfrastructureProfilePayload['variables'];
};

const initialProfileFormState: ProfileFormState = {
  id: '',
  name: '',
  category: '',
  description: '',
  tags_text: '',
  steps: [
    {
      id: 'package-docker-engine-1',
      kind: 'package',
      type: 'package',
      reference_id: 'docker-engine',
      target: 'docker-engine',
      name: 'Install Docker Engine',
      enabled: true,
    },
    {
      id: 'action-docker-status-2',
      kind: 'action',
      type: 'action',
      reference_id: 'docker-status',
      target: 'docker-status',
      name: 'Check Docker Service',
      enabled: true,
    },
  ],
  variables: [],
};

export function ProfilesPage() {
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [identityUsers, setIdentityUsers] = useState<LinuxUser[]>([]);
  const [identityGroups, setIdentityGroups] = useState<LinuxGroup[]>([]);
  const [identityPermissions, setIdentityPermissions] = useState<PermissionTemplate[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [selectedServerId, setSelectedServerId] = useState('');
  const [selectedServerIds, setSelectedServerIds] = useState<string[]>([]);
  const [formState, setFormState] = useState<ProfileFormState>(initialProfileFormState);
  const [result, setResult] = useState<ApplyProfileResult | null>(null);
  const [bulkResult, setBulkResult] = useState<ApplyProfileBulkResult | null>(null);
  const [isExecutionModalOpen, setIsExecutionModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isApplying, setIsApplying] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const [search, setSearch] = useState('');
  const targetSelector = useTargetSelection('single');

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? profiles[0] ?? null,
    [profiles, selectedProfileId],
  );
  const filteredProfiles = useMemo(
    () =>
      profiles.filter((profile) =>
        matchesSearch(search, [
          profile.id,
          profile.name,
          profile.category,
          profile.description,
          profile.tags,
          profile.steps,
          profile.variables,
        ]),
      ),
    [profiles, search],
  );

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [
        nextProfiles,
        nextServers,
        nextPackages,
        nextActions,
        nextCredentials,
        nextDeployments,
        nextIdentityUsers,
        nextIdentityGroups,
        nextIdentityPermissions,
      ] = await Promise.all([
        listProfiles(),
        listServers(),
        listPackageDefinitions(),
        listOperationalActions(),
        listCredentials(),
        listDeployments(),
        listLinuxUsers(),
        listLinuxGroups(),
        listPermissionTemplates(),
      ]);
      setProfiles(nextProfiles);
      setServers(nextServers);
      setPackages(nextPackages);
      setActions(nextActions);
      setCredentials(nextCredentials);
      setDeployments(nextDeployments);
      setIdentityUsers(nextIdentityUsers);
      setIdentityGroups(nextIdentityGroups);
      setIdentityPermissions(nextIdentityPermissions);
      setSelectedProfileId((current) => current || nextProfiles[0]?.id || '');
      setSelectedServerId((current) => current || nextServers[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  function updateField(name: keyof ProfileFormState, value: string) {
    setFormState((current) => ({ ...current, [name]: value }));
    setError(null);
    setSuccess(null);
  }

  function startEdit(profile: InfrastructureProfile) {
    setIsBuilderOpen(true);
    setEditingProfileId(profile.id);
    setFormState({
      id: profile.id,
      name: profile.name,
      category: profile.category,
      description: profile.description,
      tags_text: profile.tags.join(','),
      steps: normalizeProfileSteps(profile.steps),
      variables: profile.variables,
    });
    setError(null);
    setSuccess(null);
  }

  function resetEditor() {
    setEditingProfileId(null);
    setFormState(initialProfileFormState);
    setIsBuilderOpen(false);
  }

  async function handleCreateProfile() {
    if (!formState.id.trim() || !formState.name.trim()) {
      setError('Profile id and name are required.');
      return;
    }

    const steps = normalizeProfileSteps(formState.steps);
    if (steps.length === 0) {
      setError('Add at least one profile step.');
      return;
    }

    setIsCreating(true);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        name: formState.name.trim(),
        category: formState.category.trim() || 'Custom',
        description: formState.description.trim() || 'Custom infrastructure profile.',
        tags: splitCsv(formState.tags_text),
        steps,
        variables: formState.variables
          .filter((variable) => variable.name.trim())
          .map((variable) => ({
            ...variable,
            name: variable.name.trim(),
            description: variable.description.trim(),
          })),
      };
      if (editingProfileId) {
        const updated = await updateProfile(editingProfileId, payload);
        setProfiles((current) =>
          current.map((profile) => (profile.id === updated.id ? updated : profile)),
        );
        setSelectedProfileId(updated.id);
        setSuccess(`Updated profile ${updated.name}.`);
      } else {
        const created = await createProfile({ id: formState.id.trim(), ...payload });
        setProfiles((current) => [...current, created]);
        setSelectedProfileId(created.id);
        setSuccess(`Created profile ${created.name}.`);
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

  async function handleCloneProfile(profile: InfrastructureProfile) {
    const id = window.prompt('Clone profile as ID', `${profile.id}-copy`);
    if (!id) {
      return;
    }
    try {
      const cloned = await cloneProfile(profile.id, {
        id: id.trim(),
        name: `${profile.name} Copy`,
      });
      setProfiles((current) => [...current, cloned]);
      setSelectedProfileId(cloned.id);
      setSuccess(`Cloned profile ${cloned.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleResetProfile(profile: InfrastructureProfile) {
    const confirmed = window.confirm(
      `Restore ${profile.name} to the built-in default? Current edits will be discarded.`,
    );
    if (!confirmed) {
      return;
    }
    try {
      const restored = await resetProfile(profile.id);
      setProfiles((current) => current.map((item) => (item.id === restored.id ? restored : item)));
      setSelectedProfileId(restored.id);
      setSuccess(`Restored profile ${restored.name} to default.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleDeleteProfile(profileId: string) {
    const confirmed = window.confirm(`Delete profile ${profileId}?`);
    if (!confirmed) {
      return;
    }

    try {
      await deleteProfile(profileId);
      setProfiles((current) => current.filter((profile) => profile.id !== profileId));
      setSelectedProfileId((current) => (current === profileId ? '' : current));
      setSuccess(`Deleted profile ${profileId}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  function handleApplyProfile() {
    const profileId = selectedProfile?.id;
    if (!profileId || (!selectedServerId && selectedServerIds.length === 0)) {
      return;
    }
    setIsExecutionModalOpen(true);
  }

  async function runProfile(executionVariables: ExecutionVariableValues) {
    const profileId = selectedProfile?.id;
    if (!profileId) {
      return;
    }
    setIsApplying(true);
    setError(null);
    setResult(null);
    setBulkResult(null);

    try {
      if (selectedServerIds.length > 0) {
        setBulkResult(
          await applyProfileBulk({
            profile_id: profileId,
            target_server_ids: selectedServerIds,
            stop_on_failure: true,
            variables: executionVariables.variables,
            credential_refs: executionVariables.credential_refs,
            execution_credential_ref: executionVariables.execution_credential_ref,
          }),
        );
      } else {
        setResult(
          await applyProfile(profileId, {
            target_server_id: selectedServerId,
            stop_on_failure: true,
            variables: executionVariables.variables,
            credential_refs: executionVariables.credential_refs,
            execution_credential_ref: executionVariables.execution_credential_ref,
          }),
        );
      }
      setIsExecutionModalOpen(false);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsApplying(false);
    }
  }

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Infrastructure Profiles"
        description="Reusable infrastructure standards that apply ordered package and action workflows."
        actions={
          <PageActionButton icon={Plus} tone="secondary" onClick={() => setIsBuilderOpen(true)}>
            Create profile
          </PageActionButton>
        }
      />

      {error ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {success}
        </p>
      ) : null}
      {isLoading ? <LoadingGrid /> : null}

      {!isLoading && !error ? (
        <>
          <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
            <div className="grid gap-4 lg:grid-cols-[minmax(220px,0.8fr)_minmax(260px,1fr)_auto] lg:items-end">
              <label className="block">
                <span className="text-sm font-medium text-zinc-950">Profile</span>
                <select
                  className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-950/10"
                  value={selectedProfile?.id ?? ''}
                  onChange={(event) => setSelectedProfileId(event.target.value)}
                >
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </label>

              <button
                className="inline-flex h-10 items-center justify-center rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
                disabled={
                  !selectedProfile ||
                  (!selectedServerId && selectedServerIds.length === 0) ||
                  isApplying
                }
                type="button"
                onClick={handleApplyProfile}
              >
                {isApplying
                  ? 'Applying'
                  : selectedServerIds.length > 0
                    ? `Apply to ${selectedServerIds.length}`
                    : 'Apply profile'}
              </button>
            </div>

            <div className="mt-4">
              <TargetSelector
                servers={servers}
                eligibility="profiles"
                selection={{
                  mode: targetSelector.selection.mode,
                  selectedId: selectedServerId,
                  selectedIds: selectedServerIds,
                }}
                filters={targetSelector.filters}
                title="Profile targets"
                description="Apply this profile to one host or a filtered group of inventory hosts."
                onFiltersChange={targetSelector.setFilters}
                onSelectionChange={(selection) => {
                  targetSelector.setMode(selection.mode);
                  setSelectedServerId(selection.selectedId);
                  setSelectedServerIds(selection.selectedIds);
                }}
              />
            </div>
          </section>

          <ContextDrawer
            description="Profiles are orchestration blueprints: ordered package, deployment, action, and command standards."
            isOpen={isBuilderOpen}
            title={editingProfileId ? 'Edit Profile' : 'Create Profile'}
            width="2xl"
            onClose={resetEditor}
          >
            <ProfileBuilder
              actions={actions}
              formState={formState}
              credentials={credentials}
              deployments={deployments}
              editingProfileId={editingProfileId}
              identityGroups={identityGroups}
              identityPermissions={identityPermissions}
              identityUsers={identityUsers}
              isCreating={isCreating}
              packages={packages}
              onCreate={handleCreateProfile}
              onCancel={resetEditor}
              onFieldChange={updateField}
              onStepsChange={(steps) => setFormState((current) => ({ ...current, steps }))}
              onVariablesChange={(variables) =>
                setFormState((current) => ({ ...current, variables }))
              }
            />
          </ContextDrawer>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.8fr)]">
            <div className="grid gap-4">
              <SearchField
                placeholder="Search profiles, steps, variables..."
                value={search}
                onChange={setSearch}
              />
              {filteredProfiles.map((profile) => (
                <ProfileCard
                  key={profile.id}
                  isSelected={selectedProfile?.id === profile.id}
                  profile={profile}
                  onDelete={handleDeleteProfile}
                  onClone={handleCloneProfile}
                  onEdit={startEdit}
                  onReset={handleResetProfile}
                  onSelect={() => setSelectedProfileId(profile.id)}
                />
              ))}
              {!filteredProfiles.length ? (
                <p className="rounded-md border border-dashed border-zinc-300 bg-white p-6 text-sm text-zinc-500">
                  No profiles match this search.
                </p>
              ) : null}
            </div>
            <div className="space-y-4">
              <ProfileResult result={result} />
              <BulkProfileResult result={bulkResult} />
            </div>
          </div>
        </>
      ) : null}
      <ExecutionVariablesModal
        credentials={credentials}
        isLoading={isApplying}
        isOpen={isExecutionModalOpen && selectedProfile !== null}
        previewItems={
          selectedProfile?.steps
            .filter((step) => step.enabled !== false)
            .map((step) => step.name) ?? []
        }
        targetLabel={`${selectedServerIds.length || 1} host(s) selected`}
        title={selectedProfile ? `Apply ${selectedProfile.name}` : 'Apply profile'}
        variables={selectedProfile?.variables ?? []}
        showExecutionCredential
        onCancel={() => setIsExecutionModalOpen(false)}
        onConfirm={runProfile}
      />
    </div>
  );
}

function BulkProfileResult({ result }: { result: ApplyProfileBulkResult | null }) {
  if (!result) {
    return null;
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">Bulk profile result</h3>
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
            {item.result ? (
              <p className="mt-1 text-xs text-zinc-500">
                {item.result.jobs.length} job(s), status {item.result.status}
              </p>
            ) : null}
            {item.error ? (
              <p className="mt-1 font-mono text-xs text-zinc-500">{item.error}</p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function ProfileCard({
  profile,
  isSelected,
  onDelete,
  onClone,
  onEdit,
  onReset,
  onSelect,
}: {
  profile: InfrastructureProfile;
  isSelected: boolean;
  onDelete: (profileId: string) => void;
  onClone: (profile: InfrastructureProfile) => void;
  onEdit: (profile: InfrastructureProfile) => void;
  onReset: (profile: InfrastructureProfile) => void;
  onSelect: () => void;
}) {
  return (
    <article
      className={`rounded-lg border bg-white p-5 shadow-sm transition hover:border-zinc-300 hover:shadow-md ${isSelected ? 'border-zinc-950 ring-1 ring-zinc-950' : 'border-zinc-200'}`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-zinc-950">{profile.name}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">{profile.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex w-fit rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
            {profile.category}
          </span>
          <span className="inline-flex w-fit rounded-full bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-600 ring-1 ring-inset ring-zinc-200">
            {profile.is_builtin ? 'Built-in' : 'Custom'}
          </span>
          {profile.is_modified ? <Badge label="Modified" /> : null}
          {profile.source_template_id && !profile.is_builtin ? <Badge label="Cloned" /> : null}
        </div>
      </div>

      <ol className="mt-5 space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3">
        {profile.steps.map((step, index) => (
          <li
            key={step.id}
            className="flex items-center gap-3 rounded-md bg-white px-2 py-2 text-sm text-zinc-700 ring-1 ring-zinc-100"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-zinc-950 text-xs font-semibold text-white">
              {index + 1}
            </span>
            <span>{step.name}</span>
            <span className="rounded-full bg-zinc-50 px-2 py-0.5 text-xs text-zinc-500 ring-1 ring-zinc-200">
              {step.kind}
            </span>
            {step.kind === 'command' ? (
              <span className="truncate font-mono text-xs text-zinc-500">{step.command}</span>
            ) : null}
          </li>
        ))}
      </ol>
      {profile.variables.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {profile.variables.map((variable) => (
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
      ) : null}
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={() => onClone(profile)}
        >
          Clone
        </button>
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={() => onEdit(profile)}
        >
          Edit
        </button>
        {profile.is_builtin && profile.is_modified ? (
          <button
            className="rounded-md border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-700 transition hover:bg-amber-50"
            type="button"
            onClick={() => onReset(profile)}
          >
            Restore default
          </button>
        ) : null}
        {!profile.is_builtin ? (
          <button
            className="rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-50"
            type="button"
            onClick={() => onDelete(profile.id)}
          >
            Delete
          </button>
        ) : null}
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
          type="button"
          onClick={onSelect}
        >
          Select
        </button>
      </div>
    </article>
  );
}

function ProfileBuilder({
  actions,
  credentials,
  deployments,
  formState,
  editingProfileId,
  identityGroups,
  identityPermissions,
  identityUsers,
  isCreating,
  packages,
  onCreate,
  onCancel,
  onFieldChange,
  onStepsChange,
  onVariablesChange,
}: {
  actions: OperationalAction[];
  credentials: Credential[];
  deployments: Deployment[];
  formState: ProfileFormState;
  editingProfileId: string | null;
  identityGroups: LinuxGroup[];
  identityPermissions: PermissionTemplate[];
  identityUsers: LinuxUser[];
  isCreating: boolean;
  packages: PackageDefinition[];
  onCreate: () => void;
  onCancel: () => void;
  onFieldChange: (name: keyof ProfileFormState, value: string) => void;
  onStepsChange: (steps: ProfileStep[]) => void;
  onVariablesChange: (variables: ProfileFormState['variables']) => void;
}) {
  const previewSteps = normalizeProfileSteps(formState.steps);

  function reorderSteps(from: number, to: number) {
    if (from === to) {
      return;
    }
    const next = [...previewSteps];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    onStepsChange(next);
  }

  function updateStep(index: number, patch: Partial<ProfileStep>) {
    const next = [...previewSteps];
    const current = next[index];
    const kind = (patch.kind ?? current.kind) as ProfileStep['kind'];
    const referenceId = patch.reference_id ?? patch.target ?? current.reference_id;
    next[index] = {
      ...current,
      ...patch,
      kind,
      type: kind === 'command' ? 'script' : kind === 'script' ? 'script' : kind,
      reference_id: referenceId,
      target: referenceId,
      id: patch.id ?? current.id,
    };
    onStepsChange(next);
  }

  function addStep() {
    const index = previewSteps.length + 1;
    onStepsChange([
      ...previewSteps,
      {
        id: `package-${index}`,
        kind: 'package',
        type: 'package',
        reference_id: packages[0]?.id ?? '',
        target: packages[0]?.id ?? '',
        name: packages[0]?.name ?? 'Package step',
        enabled: true,
      },
    ]);
  }

  function removeStep(index: number) {
    onStepsChange(previewSteps.filter((_, currentIndex) => currentIndex !== index));
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">
        {editingProfileId ? 'Edit profile' : 'Build profile'}
      </h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <TextInput
          className="xl:col-span-1"
          label="ID"
          name="id"
          placeholder="custom-profile"
          value={formState.id}
          onChange={onFieldChange}
        />
        <TextInput
          className="xl:col-span-2"
          label="Name"
          name="name"
          placeholder="Custom Profile"
          value={formState.name}
          onChange={onFieldChange}
        />
        <TextInput
          className="xl:col-span-1"
          label="Category"
          name="category"
          placeholder="Baseline"
          value={formState.category}
          onChange={onFieldChange}
        />
        <TextInput
          className="xl:col-span-1"
          label="Tags"
          name="tags_text"
          placeholder="baseline,linux"
          value={formState.tags_text}
          onChange={onFieldChange}
        />
        <TextInput
          className="md:col-span-2 xl:col-span-3"
          label="Description"
          name="description"
          placeholder="Reusable host standard"
          value={formState.description}
          onChange={onFieldChange}
        />
        <div className="xl:col-span-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase text-zinc-500">Execution steps</p>
            <button
              className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
              type="button"
              onClick={addStep}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add step
            </button>
          </div>
          <ol className="mt-3 space-y-3">
            {previewSteps.map((step, index) => (
              <ProfileStepCard
                key={`${step.id}-${index}`}
                actions={actions}
                credentials={credentials}
                deployments={deployments}
                identityGroups={identityGroups}
                identityPermissions={identityPermissions}
                identityUsers={identityUsers}
                index={index}
                packages={packages}
                step={step}
                total={previewSteps.length}
                onMove={reorderSteps}
                onRemove={() => removeStep(index)}
                onUpdate={(patch) => updateStep(index, patch)}
              />
            ))}
          </ol>
        </div>
        <VariableDefinitionEditor credentials={credentials} variables={formState.variables} onChange={onVariablesChange} />
      </div>
      <div className="mt-4 grid gap-4 text-xs text-zinc-500 lg:grid-cols-2">
        <ReferenceList
          label="Package refs"
          values={packages.map((packageDefinition) => packageDefinition.id)}
        />
        <ReferenceList label="Action refs" values={actions.map((action) => action.id)} />
        <ReferenceList
          label="Deployment refs"
          values={deployments.map((deployment) => deployment.id)}
        />
        <ReferenceList label="Identity users" values={identityUsers.map((user) => user.username)} />
        <ReferenceList label="Identity groups" values={identityGroups.map((group) => group.name)} />
        <ReferenceList
          label="Identity permissions"
          values={identityPermissions.map((permission) => permission.path)}
        />
      </div>
      <div className="mt-4 flex justify-end gap-2">
        {editingProfileId ? (
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
          {isCreating ? 'Saving' : editingProfileId ? 'Save profile' : 'Create profile'}
        </button>
      </div>
    </section>
  );
}

function ReferenceList({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <div className="font-semibold text-zinc-700">{label}</div>
      <div className="mt-1 flex flex-wrap gap-1">
        {values.map((value) => (
          <span key={value} className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-zinc-600">
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

type StepOption = { id: string; name: string };

function stepOptions(
  stepType: string,
  {
    actions,
    deployments,
    identityGroups,
    identityPermissions,
    identityUsers,
    packages,
  }: {
    actions: OperationalAction[];
    deployments: Deployment[];
    identityGroups: LinuxGroup[];
    identityPermissions: PermissionTemplate[];
    identityUsers: LinuxUser[];
    packages: PackageDefinition[];
  },
): StepOption[] {
  if (stepType === 'action') return actions.map((action) => ({ id: action.id, name: action.name }));
  if (stepType === 'deployment') return deployments.map((deployment) => ({ id: deployment.id, name: deployment.name }));
  if (stepType === 'identity_user') return identityUsers.map((user) => ({ id: user.id, name: user.username }));
  if (stepType === 'identity_group') return identityGroups.map((group) => ({ id: group.id, name: group.name }));
  if (stepType === 'identity_permission') return identityPermissions.map((permission) => ({ id: permission.id, name: permission.path }));
  return packages.map((packageDefinition) => ({ id: packageDefinition.id, name: packageDefinition.name }));
}

function ProfileStepCard({
  actions,
  credentials,
  deployments,
  identityGroups,
  identityPermissions,
  identityUsers,
  index,
  packages,
  step,
  total,
  onMove,
  onRemove,
  onUpdate,
}: {
  actions: OperationalAction[];
  credentials: Credential[];
  deployments: Deployment[];
  identityGroups: LinuxGroup[];
  identityPermissions: PermissionTemplate[];
  identityUsers: LinuxUser[];
  index: number;
  packages: PackageDefinition[];
  step: ProfileStep;
  total: number;
  onMove: (from: number, to: number) => void;
  onRemove: () => void;
  onUpdate: (patch: Partial<ProfileStep>) => void;
}) {
  const stepType = step.kind === 'command' ? 'script' : step.kind;
  const options = stepOptions(stepType, {
    actions,
    deployments,
    identityGroups,
    identityPermissions,
    identityUsers,
    packages,
  });
  const Icon = stepType === 'package'
    ? Package
    : stepType === 'action'
      ? Play
      : stepType.startsWith('identity_')
        ? stepType === 'identity_permission'
          ? ShieldCheck
          : UsersRound
        : Terminal;

  function handleTypeChange(value: string) {
    const nextKind = value === 'script' ? 'command' : (value as ProfileStep['kind']);
    const nextOptions = stepOptions(value, {
      actions,
      deployments,
      identityGroups,
      identityPermissions,
      identityUsers,
      packages,
    });
    const first = nextOptions[0];
    onUpdate({
      kind: nextKind,
      type: value as ProfileStep['type'],
      reference_id: value === 'script' ? step.id : (first?.id ?? ''),
      target: value === 'script' ? step.id : (first?.id ?? ''),
      name: value === 'script' ? 'Script step' : (first?.name ?? ''),
      command: value === 'script' ? (step.command ?? '') : null,
    });
  }

  function handleTargetChange(value: string) {
    const selected = options.find((option) => option.id === value);
    onUpdate({ reference_id: value, target: value, name: selected?.name ?? value });
  }

  return (
    <li
      className={`rounded-md border bg-white p-4 ${step.enabled === false ? 'border-zinc-200 opacity-60' : 'border-zinc-300'}`}
      draggable
      onDragStart={(event: DragEvent<HTMLLIElement>) =>
        event.dataTransfer.setData('text/plain', String(index))
      }
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        onMove(Number(event.dataTransfer.getData('text/plain')), index);
      }}
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(14rem,1.1fr)_minmax(0,4fr)_auto] xl:items-start">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-zinc-950 text-white">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 space-y-2">
            <p className="truncate text-sm font-semibold text-zinc-950">{step.name}</p>
            <p className="text-xs text-zinc-500">Step {index + 1}</p>
            <label className="inline-flex h-8 w-fit items-center gap-2 rounded-md border border-zinc-300 px-2.5 text-xs font-semibold text-zinc-700">
              <input
                className="h-4 w-4 shrink-0"
                checked={step.enabled !== false}
                type="checkbox"
                onChange={(event) => onUpdate({ enabled: event.target.checked })}
              />
              Enabled
            </label>
          </div>
        </div>

        <div className="grid min-w-0 gap-3 md:grid-cols-2 xl:grid-cols-[minmax(9rem,0.8fr)_minmax(20rem,2.4fr)_minmax(12rem,1fr)]">
          <label className="min-w-0 text-xs font-medium text-zinc-700">
            Type
            <select
              className="mt-1 w-full min-w-0 truncate rounded-md border border-zinc-300 bg-white px-2 py-2 pr-9 text-sm"
              value={stepType}
              onChange={(event) => handleTypeChange(event.target.value)}
            >
              <option value="package">Package</option>
              <option value="action">Action</option>
              <option value="deployment">Deployment</option>
              <option value="identity_user">Identity user</option>
              <option value="identity_group">Identity group</option>
              <option value="identity_permission">Identity permission</option>
              <option value="script">Script</option>
            </select>
          </label>

          {stepType === 'script' ? (
            <label className="min-w-0 text-xs font-medium text-zinc-700 md:col-span-2">
              Command
              <input
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 font-mono text-sm"
                value={step.command ?? ''}
                onChange={(event) => onUpdate({ command: event.target.value, name: 'Script step' })}
              />
            </label>
          ) : (
            <label className="min-w-0 text-xs font-medium text-zinc-700">
              Target
              <select
                className="mt-1 w-full min-w-0 truncate rounded-md border border-zinc-300 bg-white px-2 py-2 pr-9 text-sm"
                value={step.reference_id}
                onChange={(event) => handleTargetChange(event.target.value)}
              >
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="min-w-0 text-xs font-medium text-zinc-700">
            Credential
            <select
              className="mt-1 w-full min-w-[12rem] truncate rounded-md border border-zinc-300 bg-white px-2 py-2 pr-10 text-sm"
              value={step.credential_ref ?? ''}
              onChange={(event) => onUpdate({ credential_ref: event.target.value || null })}
            >
              <option value="">None</option>
              {credentials.map((credential) => (
                <option key={credential.id} value={credential.id}>
                  {credential.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex shrink-0 items-start justify-end gap-2">
          <button
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-zinc-300 text-zinc-700 disabled:opacity-40"
            disabled={index === 0}
            type="button"
            onClick={() => onMove(index, index - 1)}
            title="Move up"
          >
            <ArrowUp className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-zinc-300 text-zinc-700 disabled:opacity-40"
            disabled={index === total - 1}
            type="button"
            onClick={() => onMove(index, index + 1)}
            title="Move down"
          >
            <ArrowDown className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-rose-300 text-rose-700 hover:bg-rose-50"
            type="button"
            onClick={onRemove}
            title="Remove step"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </li>
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
  className = '',
  label,
  name,
  value,
  placeholder,
  onChange,
}: {
  className?: string;
  label: string;
  name: keyof ProfileFormState;
  value: string;
  placeholder: string;
  onChange: (name: keyof ProfileFormState, value: string) => void;
}) {
  return (
    <label className={`min-w-0 text-sm font-medium text-zinc-700 ${className}`}>
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

function ProfileResult({ result }: { result: ApplyProfileResult | null }) {
  if (!result) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Execution sequence</h3>
        <p className="mt-2 text-sm text-zinc-500">
          Apply a profile to see generated jobs and results.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">Execution sequence</h3>
        <p className="mt-1 text-sm text-zinc-500">{result.message}</p>
      </div>
      <div className="divide-y divide-zinc-100">
        {result.jobs.map((job, index) => (
          <div key={job.id} className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-zinc-950">Step {index + 1}</p>
                <p className="mt-1 break-all font-mono text-xs text-zinc-500">{job.command}</p>
              </div>
              <JobStatusBadge status={job.status} />
            </div>
            <pre className="mt-3 max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-50">
              {job.stdout?.trim() || job.stderr?.trim() || '(empty)'}
            </pre>
          </div>
        ))}
      </div>
    </section>
  );
}

function LoadingGrid() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-56 animate-pulse rounded-lg bg-zinc-100" />
      ))}
    </div>
  );
}

function splitCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeProfileSteps(steps: ProfileStep[]): ProfileStep[] {
  return steps.map((step, index) => {
    const kind = step.kind === 'script' ? 'command' : step.kind;
    const referenceId = step.reference_id || step.target || step.id || `${kind}-${index + 1}`;
    return {
      ...step,
      id: step.id || `${kind}-${referenceId}-${index + 1}`,
      kind,
      type: step.type ?? (kind === 'command' ? 'script' : kind),
      reference_id: referenceId,
      target: step.target ?? referenceId,
      name: step.name || referenceId,
      enabled: step.enabled ?? true,
      credential_ref: step.credential_ref ?? null,
    };
  });
}
