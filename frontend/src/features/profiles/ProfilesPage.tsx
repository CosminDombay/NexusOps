import { useCallback, useEffect, useMemo, useState } from 'react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listServers } from '../inventory/api/serversApi';
import type { Server } from '../inventory/types/server';
import { listOperationalActions } from '../jobs/api/jobsApi';
import { JobStatusBadge } from '../jobs/components/JobStatusBadge';
import type { OperationalAction } from '../jobs/types/job';
import { listPackageDefinitions } from '../packages/api/packagesApi';
import type { PackageDefinition } from '../packages/types/package';
import { applyProfile, createProfile, deleteProfile, listProfiles } from './api/profilesApi';
import type { ApplyProfileResult, CreateInfrastructureProfilePayload, InfrastructureProfile, ProfileStep } from './types/profile';

type ProfileFormState = Omit<CreateInfrastructureProfilePayload, 'tags' | 'steps'> & {
  tags_text: string;
  steps_text: string;
};

const initialProfileFormState: ProfileFormState = {
  id: '',
  name: '',
  category: '',
  description: '',
  tags_text: '',
  steps_text: 'package:docker-engine:Install Docker Engine\naction:docker-status:Check Docker Service',
};

export function ProfilesPage() {
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [servers, setServers] = useState<Server[]>([]);
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [actions, setActions] = useState<OperationalAction[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [selectedServerId, setSelectedServerId] = useState('');
  const [formState, setFormState] = useState<ProfileFormState>(initialProfileFormState);
  const [result, setResult] = useState<ApplyProfileResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isApplying, setIsApplying] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? profiles[0] ?? null,
    [profiles, selectedProfileId],
  );

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [nextProfiles, nextServers, nextPackages, nextActions] = await Promise.all([
        listProfiles(),
        listServers(),
        listPackageDefinitions(),
        listOperationalActions(),
      ]);
      setProfiles(nextProfiles);
      setServers(nextServers);
      setPackages(nextPackages);
      setActions(nextActions);
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

  async function handleCreateProfile() {
    if (!formState.id.trim() || !formState.name.trim()) {
      setError('Profile id and name are required.');
      return;
    }

    const steps = parseSteps(formState.steps_text);
    if (steps.length === 0) {
      setError('Add at least one profile step.');
      return;
    }

    setIsCreating(true);
    setError(null);
    setSuccess(null);

    try {
      const created = await createProfile({
        id: formState.id.trim(),
        name: formState.name.trim(),
        category: formState.category.trim() || 'Custom',
        description: formState.description.trim() || 'Custom infrastructure profile.',
        tags: splitCsv(formState.tags_text),
        steps,
      });
      setProfiles((current) => [...current, created]);
      setSelectedProfileId(created.id);
      setFormState(initialProfileFormState);
      setSuccess(`Created profile ${created.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsCreating(false);
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

  async function handleApplyProfile() {
    const profileId = selectedProfile?.id;
    if (!profileId || !selectedServerId) {
      return;
    }

    const confirmed = window.confirm(`Apply ${selectedProfile.name} to the selected host?`);
    if (!confirmed) {
      return;
    }

    setIsApplying(true);
    setError(null);

    try {
      setResult(
        await applyProfile(profileId, {
          target_server_id: selectedServerId,
          stop_on_failure: true,
        }),
      );
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
      />

      {error ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</p> : null}
      {success ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">{success}</p> : null}
      {isLoading ? <LoadingGrid /> : null}

      {!isLoading && !error ? (
        <>
          <ProfileBuilder
            actions={actions}
            formState={formState}
            isCreating={isCreating}
            packages={packages}
            onCreate={handleCreateProfile}
            onFieldChange={updateField}
          />

          <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
            <div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
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

              <label className="block">
                <span className="text-sm font-medium text-zinc-950">Target host</span>
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

              <button
                className="inline-flex h-10 items-center justify-center rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
                disabled={!selectedProfile || !selectedServerId || isApplying}
                type="button"
                onClick={handleApplyProfile}
              >
                {isApplying ? 'Applying' : 'Apply profile'}
              </button>
            </div>
          </section>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.8fr)]">
            <div className="grid gap-4">
              {profiles.map((profile) => (
                <ProfileCard
                  key={profile.id}
                  isSelected={selectedProfile?.id === profile.id}
                  profile={profile}
                  onDelete={handleDeleteProfile}
                  onSelect={() => setSelectedProfileId(profile.id)}
                />
              ))}
            </div>
            <ProfileResult result={result} />
          </div>
        </>
      ) : null}
    </div>
  );
}

function ProfileCard({
  profile,
  isSelected,
  onDelete,
  onSelect,
}: {
  profile: InfrastructureProfile;
  isSelected: boolean;
  onDelete: (profileId: string) => void;
  onSelect: () => void;
}) {
  return (
    <article className={`rounded-lg border bg-white p-5 shadow-sm ${isSelected ? 'border-zinc-950' : 'border-zinc-200'}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">{profile.name}</h3>
          <p className="mt-1 text-sm text-zinc-500">{profile.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex w-fit rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
            {profile.category}
          </span>
          <span className="inline-flex w-fit rounded-full bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-600 ring-1 ring-inset ring-zinc-200">
            {profile.is_builtin ? 'Built-in' : 'Custom'}
          </span>
        </div>
      </div>

      <ol className="mt-5 space-y-2">
        {profile.steps.map((step, index) => (
          <li key={step.id} className="flex items-center gap-3 text-sm text-zinc-700">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-zinc-950 text-xs font-semibold text-white">
              {index + 1}
            </span>
            <span>{step.name}</span>
            <span className="rounded-full bg-zinc-50 px-2 py-0.5 text-xs text-zinc-500 ring-1 ring-zinc-200">
              {step.kind}
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-5 flex justify-end gap-2">
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
  formState,
  isCreating,
  packages,
  onCreate,
  onFieldChange,
}: {
  actions: OperationalAction[];
  formState: ProfileFormState;
  isCreating: boolean;
  packages: PackageDefinition[];
  onCreate: () => void;
  onFieldChange: (name: keyof ProfileFormState, value: string) => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">Build profile</h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TextInput label="ID" name="id" placeholder="custom-profile" value={formState.id} onChange={onFieldChange} />
        <TextInput label="Name" name="name" placeholder="Custom Profile" value={formState.name} onChange={onFieldChange} />
        <TextInput label="Category" name="category" placeholder="Baseline" value={formState.category} onChange={onFieldChange} />
        <TextInput label="Tags" name="tags_text" placeholder="baseline,linux" value={formState.tags_text} onChange={onFieldChange} />
        <TextInput label="Description" name="description" placeholder="Reusable host standard" value={formState.description} onChange={onFieldChange} />
        <label className="text-sm font-medium text-zinc-700 xl:col-span-3">
          Steps
          <textarea
            className="mt-1 min-h-32 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 font-mono text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
            value={formState.steps_text}
            onChange={(event) => onFieldChange('steps_text', event.target.value)}
          />
        </label>
      </div>
      <div className="mt-4 grid gap-4 text-xs text-zinc-500 lg:grid-cols-2">
        <ReferenceList label="Package refs" values={packages.map((packageDefinition) => packageDefinition.id)} />
        <ReferenceList label="Action refs" values={actions.map((action) => action.id)} />
      </div>
      <div className="mt-4 flex justify-end">
        <button
          className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
          disabled={isCreating}
          type="button"
          onClick={onCreate}
        >
          {isCreating ? 'Creating' : 'Create profile'}
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

function TextInput({
  label,
  name,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  name: keyof ProfileFormState;
  value: string;
  placeholder: string;
  onChange: (name: keyof ProfileFormState, value: string) => void;
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

function ProfileResult({ result }: { result: ApplyProfileResult | null }) {
  if (!result) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Execution sequence</h3>
        <p className="mt-2 text-sm text-zinc-500">Apply a profile to see generated jobs and results.</p>
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

function parseSteps(value: string): ProfileStep[] {
  return value
    .split('\n')
    .map((line, index) => {
      const [kind, referenceId, name] = line.split(':').map((part) => part.trim());
      if ((kind !== 'action' && kind !== 'package') || !referenceId) {
        return null;
      }
      return {
        id: `${kind}-${referenceId}-${index + 1}`,
        kind,
        reference_id: referenceId,
        name: name || referenceId,
      };
    })
    .filter((step): step is ProfileStep => step !== null);
}
