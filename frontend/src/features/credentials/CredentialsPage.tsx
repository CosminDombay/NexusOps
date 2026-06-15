import { Eye, KeyRound, Link2, Loader2, Plus, RotateCcw, Trash2, X } from 'lucide-react';
import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton } from '../../components/operations/OperationalComponents';
import { SearchField } from '../../components/search/SearchField';
import { getApiErrorMessage } from '../../lib/api/client';
import { matchesSearch } from '../../lib/search/match';
import {
  createCredential,
  deleteCredential,
  getCredentialUsage,
  listDeletedCredentials,
  listCredentials,
  purgeCredential,
  restoreCredential,
  updateCredential,
} from './api/credentialsApi';
import type { Credential, CredentialReference, CredentialScope, CredentialType } from './types/credential';

type FormState = {
  name: string;
  description: string;
  credential_type: CredentialType;
  username: string;
  secret: string;
  tags: string;
  scope: CredentialScope;
};

const initialFormState: FormState = {
  name: '',
  description: '',
  credential_type: 'ssh_password',
  username: '',
  secret: '',
  tags: '',
  scope: 'global',
};

const credentialTypes: CredentialType[] = [
  'ssh_password',
  'ssh_key',
  'api_token',
  'password',
  'env_secret',
];
const scopes: CredentialScope[] = ['global', 'project', 'environment'];

export function CredentialsPage() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [deletedCredentials, setDeletedCredentials] = useState<Credential[]>([]);
  const [view, setView] = useState<'active' | 'trash'>('active');
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingCredentialId, setEditingCredentialId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [referencePanel, setReferencePanel] = useState<{
    credentialName: string;
    references: CredentialReference[];
  } | null>(null);
  const usesUsername =
    formState.credential_type === 'ssh_password' ||
    formState.credential_type === 'ssh_key' ||
    formState.credential_type === 'password';
  const visibleCredentials = useMemo(
    () =>
      (view === 'active' ? credentials : deletedCredentials).filter((credential) =>
        matchesSearch(search, [
          credential.name,
          credential.description,
          credential.credential_type,
          credential.username,
          credential.scope,
          credential.tags,
          credential.deleted_by,
          credential.delete_reason,
        ]),
      ),
    [credentials, deletedCredentials, search, view],
  );

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [nextCredentials, nextDeletedCredentials] = await Promise.all([
        listCredentials(),
        listDeletedCredentials(),
      ]);
      setCredentials(nextCredentials);
      setDeletedCredentials(nextDeletedCredentials);
      setReferencePanel(null);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function updateField(name: keyof FormState, value: string) {
    setFormState((current) => ({ ...current, [name]: value }));
    setError(null);
    setSuccess(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formState.name.trim() || (!editingCredentialId && !formState.secret.trim())) {
      setError(editingCredentialId ? 'Name is required.' : 'Name and secret are required.');
      return;
    }

    setIsSaving(true);
    try {
      const payload = {
        name: formState.name.trim(),
        description: formState.description.trim(),
        credential_type: formState.credential_type,
        username: usesUsername ? formState.username.trim() || null : null,
        secret: formState.credential_type === 'ssh_key' ? null : formState.secret,
        private_key: formState.credential_type === 'ssh_key' ? formState.secret : null,
        tags: splitCsv(formState.tags),
        scope: formState.scope,
      };
      if (editingCredentialId) {
        const updated = await updateCredential(editingCredentialId, {
          ...payload,
          secret: formState.secret ? payload.secret : undefined,
          private_key: formState.secret ? payload.private_key : undefined,
        });
        setCredentials((current) =>
          current.map((credential) => (credential.id === updated.id ? updated : credential)),
        );
        setSuccess(`Updated credential ${updated.name}.`);
      } else {
        const created = await createCredential(payload);
        setCredentials((current) => [created, ...current]);
        setSuccess(`Created credential ${created.name}. Secret material is now masked.`);
      }
      closeDrawer();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(credential: Credential) {
    if (
      !window.confirm(
        `Move credential ${credential.name} to Trash? Runtime operations will no longer use it until restored.`,
      )
    ) {
      return;
    }
    try {
      const deleted = await deleteCredential(credential.id, 'Deleted from Credential Manager UI');
      setCredentials((current) => current.filter((item) => item.id !== credential.id));
      setDeletedCredentials((current) => [deleted, ...current]);
      setReferencePanel(null);
      setSuccess(`Moved credential ${credential.name} to Trash.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleRestore(credential: Credential) {
    try {
      const restored = await restoreCredential(credential.id);
      setDeletedCredentials((current) => current.filter((item) => item.id !== credential.id));
      setCredentials((current) => [restored, ...current]);
      setReferencePanel(null);
      setSuccess(`Restored credential ${credential.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handlePurge(credential: Credential) {
    if (
      !window.confirm(
        `Permanently delete credential ${credential.name}? This cannot be undone and is blocked while references exist.`,
      )
    ) {
      return;
    }
    try {
      await purgeCredential(credential.id);
      setDeletedCredentials((current) => current.filter((item) => item.id !== credential.id));
      setReferencePanel(null);
      setSuccess(`Permanently deleted credential ${credential.name}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  async function handleShowUsage(credential: Credential) {
    try {
      const usage = await getCredentialUsage(credential.id);
      setReferencePanel({
        credentialName: credential.name,
        references: usage.references,
      });
      setError(null);
      setSuccess(null);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  function openCreateDrawer() {
    setEditingCredentialId(null);
    setFormState(initialFormState);
    setIsCreateOpen(true);
    setError(null);
    setSuccess(null);
    setReferencePanel(null);
  }

  function openEditDrawer(credential: Credential) {
    setEditingCredentialId(credential.id);
    setFormState({
      name: credential.name,
      description: credential.description,
      credential_type: credential.credential_type,
      username: credential.username ?? '',
      secret: '',
      tags: credential.tags.join(','),
      scope: credential.scope,
    });
    setIsCreateOpen(true);
    setError(null);
    setSuccess(null);
    setReferencePanel(null);
  }

  function closeDrawer() {
    setEditingCredentialId(null);
    setFormState(initialFormState);
    setIsCreateOpen(false);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Credentials"
        description="Reusable SSH accounts, tokens, and secrets for server-side orchestration."
        actions={
          <PageActionButton icon={Plus} tone="secondary" onClick={openCreateDrawer}>
            Create credential
          </PageActionButton>
        }
      />

      {error ? (
        <p className="whitespace-pre-line rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {success}
        </p>
      ) : null}
      {referencePanel ? (
        <ReferencePanel
          credentialName={referencePanel.credentialName}
          references={referencePanel.references}
          onClose={() => setReferencePanel(null)}
        />
      ) : null}

      <ContextDrawer
        description={
          editingCredentialId
            ? 'Update metadata or provide replacement secret material. Leave the secret empty to keep the stored value.'
            : 'Secrets are encrypted by the backend and never returned after save.'
        }
        isOpen={isCreateOpen}
        title={editingCredentialId ? 'Edit Credential' : 'Create Credential'}
        width="lg"
        onClose={closeDrawer}
      >
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <TextInput
              label="Name"
              value={formState.name}
              onChange={(value) => updateField('name', value)}
              placeholder="linux-admin-default"
            />
            {usesUsername ? (
              <TextInput
                label="Username"
                value={formState.username}
                onChange={(value) => updateField('username', value)}
                placeholder="ubuntu"
              />
            ) : (
              <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500">
                Username is not used for this credential type.
              </div>
            )}
            <label className="text-sm font-medium text-zinc-700">
              Type
              <select
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
                value={formState.credential_type}
                onChange={(event) => updateField('credential_type', event.target.value)}
              >
                {credentialTypes.map((type) => (
                  <option key={type} value={type}>
                    {type.replace('_', ' ')}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium text-zinc-700">
              Scope
              <select
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
                value={formState.scope}
                onChange={(event) => updateField('scope', event.target.value)}
              >
                {scopes.map((scope) => (
                  <option key={scope} value={scope}>
                    {scope}
                  </option>
                ))}
              </select>
            </label>
            <TextInput
              label="Tags"
              value={formState.tags}
              onChange={(value) => updateField('tags', value)}
              placeholder="linux,shared"
            />
            <TextInput
              label="Description"
              value={formState.description}
              onChange={(value) => updateField('description', value)}
              placeholder="Shared admin account"
            />
            <label className="text-sm font-medium text-zinc-700 md:col-span-2 xl:col-span-3">
              {formState.credential_type === 'ssh_key' ? 'Private key' : 'Secret'}
              <textarea
                className="mt-1 min-h-24 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 font-mono text-sm"
                value={formState.secret}
                onChange={(event) => updateField('secret', event.target.value)}
              />
            </label>
          </div>
          <div className="mt-5 flex justify-end">
            <button
              className="inline-flex items-center gap-2 rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-zinc-300"
              disabled={isSaving}
              type="submit"
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Plus className="h-4 w-4" aria-hidden="true" />
              )}
              {editingCredentialId ? 'Save credential' : 'Create credential'}
            </button>
          </div>
        </form>
      </ContextDrawer>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">
            {view === 'active' ? 'Saved credentials' : 'Credential Trash'}
          </h3>
          <div className="inline-flex rounded-md border border-zinc-300 bg-zinc-50 p-1">
            <button
              className={`rounded px-3 py-1.5 text-sm font-semibold ${view === 'active' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-600 hover:text-zinc-950'}`}
              type="button"
              onClick={() => setView('active')}
            >
              Active
            </button>
            <button
              className={`rounded px-3 py-1.5 text-sm font-semibold ${view === 'trash' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-600 hover:text-zinc-950'}`}
              type="button"
              onClick={() => setView('trash')}
            >
              Trash
            </button>
          </div>
        </div>
        <div className="border-b border-zinc-200 px-5 py-4">
          <SearchField
            placeholder="Search credentials, types, tags..."
            value={search}
            onChange={setSearch}
          />
        </div>
        {isLoading ? <p className="p-5 text-sm text-zinc-500">Loading credentials...</p> : null}
        {!isLoading && visibleCredentials.length === 0 ? (
          <p className="p-5 text-sm text-zinc-500">
            {search ? 'No credentials match this search.' : view === 'active' ? 'No credentials yet.' : 'Trash is empty.'}
          </p>
        ) : null}
        <div className="divide-y divide-zinc-100">
          {visibleCredentials.map((credential) => (
            <div
              key={credential.id}
              className="flex flex-col gap-3 px-5 py-4 transition hover:bg-zinc-50 md:flex-row md:items-center md:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <KeyRound className="h-4 w-4 text-zinc-500" aria-hidden="true" />
                  <h4 className="text-base font-semibold text-zinc-950">{credential.name}</h4>
                  <Badge label={credential.credential_type.replace('_', ' ')} />
                  <Badge label={credential.scope} />
                  {credential.reference_count ? <Badge label={`${credential.reference_count} refs`} /> : null}
                  {credential.deleted_at ? <Badge label="trashed" /> : null}
                </div>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">
                  {credential.description || 'No description'}
                </p>
                <p className="mt-1 font-mono text-xs text-zinc-500">
                  {credential.username ?? 'no username'} / {credential.masked_secret}
                </p>
                {credential.deleted_at ? (
                  <p className="mt-1 text-xs text-zinc-500">
                    Deleted {new Date(credential.deleted_at).toLocaleString()}
                    {credential.deleted_by ? ` by ${credential.deleted_by}` : ''}
                    {credential.delete_reason ? ` - ${credential.delete_reason}` : ''}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {credential.reference_count ? (
                  <button
                    className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                    type="button"
                    onClick={() => void handleShowUsage(credential)}
                  >
                    <Eye className="h-4 w-4" aria-hidden="true" />
                    References
                  </button>
                ) : null}
                {view === 'active' ? (
                  <>
                    <button
                      className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                      type="button"
                      onClick={() => openEditDrawer(credential)}
                    >
                      Edit
                    </button>
                    <button
                      className="inline-flex items-center gap-2 rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50"
                      type="button"
                      onClick={() => void handleDelete(credential)}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                      Delete
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                      type="button"
                      onClick={() => void handleRestore(credential)}
                    >
                      <RotateCcw className="h-4 w-4" aria-hidden="true" />
                      Restore
                    </button>
                    <button
                      className="inline-flex items-center gap-2 rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50"
                      type="button"
                      onClick={() => void handlePurge(credential)}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                      Permanently delete
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function TextInput({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input
        className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
      {label}
    </span>
  );
}

function ReferencePanel({
  credentialName,
  references,
  onClose,
}: {
  credentialName: string;
  references: CredentialReference[];
  onClose: () => void;
}) {
  return (
    <section className="rounded-lg border border-cyan-400/30 bg-cyan-950/20 p-4 text-sm text-cyan-50">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-3">
          <Link2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" aria-hidden="true" />
          <div>
            <h3 className="font-semibold text-cyan-100">References for {credentialName}</h3>
            <p className="mt-1 text-cyan-200/80">
              {references.length
                ? `${references.length} active record${references.length === 1 ? '' : 's'} use this credential.`
                : 'No active records use this credential.'}
            </p>
          </div>
        </div>
        <button
          type="button"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-cyan-400/30 text-cyan-100 hover:bg-cyan-900/40"
          onClick={onClose}
        >
          <span className="sr-only">Close references</span>
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      {references.length ? (
        <div className="mt-4 divide-y divide-cyan-300/10 rounded-md border border-cyan-300/20 bg-slate-950/40">
          {references.map((reference) => (
            <div
              key={`${reference.reference_type}:${reference.reference_id}:${reference.field}`}
              className="grid gap-2 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_minmax(12rem,0.5fr)]"
            >
              <div>
                <p className="font-semibold text-cyan-50">{reference.name}</p>
                <p className="mt-0.5 text-xs text-cyan-200/70">
                  {formatReferenceType(reference.reference_type)}
                  {reference.detail ? ` - ${reference.detail}` : ''}
                </p>
              </div>
              <div className="font-mono text-xs text-cyan-100/80 sm:text-right">{reference.field}</div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function formatReferenceType(value: string) {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function splitCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}
