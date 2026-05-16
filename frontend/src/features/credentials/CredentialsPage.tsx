import { KeyRound, Loader2, Plus, ShieldCheck, Trash2 } from 'lucide-react';
import { FormEvent, useCallback, useEffect, useState } from 'react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { createCredential, deleteCredential, listCredentials } from './api/credentialsApi';
import type { Credential, CredentialScope, CredentialType } from './types/credential';

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

const credentialTypes: CredentialType[] = ['ssh_password', 'ssh_key', 'api_token', 'password', 'env_secret'];
const scopes: CredentialScope[] = ['global', 'project', 'environment'];

export function CredentialsPage() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const usesUsername = formState.credential_type === 'ssh_password' || formState.credential_type === 'ssh_key' || formState.credential_type === 'password';

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setCredentials(await listCredentials());
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
    if (!formState.name.trim() || !formState.secret.trim()) {
      setError('Name and secret are required.');
      return;
    }

    setIsSaving(true);
    try {
      const created = await createCredential({
        name: formState.name.trim(),
        description: formState.description.trim(),
        credential_type: formState.credential_type,
        username: usesUsername ? formState.username.trim() || null : null,
        secret: formState.credential_type === 'ssh_key' ? null : formState.secret,
        private_key: formState.credential_type === 'ssh_key' ? formState.secret : null,
        tags: splitCsv(formState.tags),
        scope: formState.scope,
      });
      setCredentials((current) => [created, ...current]);
      setFormState(initialFormState);
      setSuccess(`Created credential ${created.name}. Secret material is now masked.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(credential: Credential) {
    if (!window.confirm(`Delete credential ${credential.name}? Assigned nodes will keep running but lose this credential reference.`)) {
      return;
    }
    try {
      await deleteCredential(credential.id);
      setCredentials((current) => current.filter((item) => item.id !== credential.id));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Credentials" description="Reusable SSH accounts, tokens, and secrets for server-side orchestration." />

      {error ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</p> : null}
      {success ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">{success}</p> : null}

      <form className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm" onSubmit={handleSubmit}>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-zinc-950 text-white">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-zinc-950">Create credential</h3>
            <p className="text-sm text-zinc-500">Secrets are encrypted by the backend and never returned after save.</p>
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <TextInput label="Name" value={formState.name} onChange={(value) => updateField('name', value)} placeholder="linux-root-default" />
          {usesUsername ? (
            <TextInput label="Username" value={formState.username} onChange={(value) => updateField('username', value)} placeholder="root or ubuntu" />
          ) : (
            <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500">
              Username is not used for this credential type.
            </div>
          )}
          <label className="text-sm font-medium text-zinc-700">
            Type
            <select className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm" value={formState.credential_type} onChange={(event) => updateField('credential_type', event.target.value)}>
              {credentialTypes.map((type) => <option key={type} value={type}>{type.replace('_', ' ')}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-zinc-700">
            Scope
            <select className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm" value={formState.scope} onChange={(event) => updateField('scope', event.target.value)}>
              {scopes.map((scope) => <option key={scope} value={scope}>{scope}</option>)}
            </select>
          </label>
          <TextInput label="Tags" value={formState.tags} onChange={(value) => updateField('tags', value)} placeholder="linux,shared" />
          <TextInput label="Description" value={formState.description} onChange={(value) => updateField('description', value)} placeholder="Shared admin account" />
          <label className="text-sm font-medium text-zinc-700 md:col-span-2 xl:col-span-3">
            {formState.credential_type === 'ssh_key' ? 'Private key' : 'Secret'}
            <textarea className="mt-1 min-h-24 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 font-mono text-sm" value={formState.secret} onChange={(event) => updateField('secret', event.target.value)} />
          </label>
        </div>
        <div className="mt-5 flex justify-end">
          <button className="inline-flex items-center gap-2 rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-zinc-300" disabled={isSaving} type="submit">
            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Plus className="h-4 w-4" aria-hidden="true" />}
            Create credential
          </button>
        </div>
      </form>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">Saved credentials</h3>
        </div>
        {isLoading ? <p className="p-5 text-sm text-zinc-500">Loading credentials...</p> : null}
        {!isLoading && credentials.length === 0 ? <p className="p-5 text-sm text-zinc-500">No credentials yet.</p> : null}
        <div className="divide-y divide-zinc-100">
          {credentials.map((credential) => (
            <div key={credential.id} className="flex flex-col gap-3 px-5 py-4 transition hover:bg-zinc-50 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <KeyRound className="h-4 w-4 text-zinc-500" aria-hidden="true" />
                  <h4 className="text-base font-semibold text-zinc-950">{credential.name}</h4>
                  <Badge label={credential.credential_type.replace('_', ' ')} />
                  <Badge label={credential.scope} />
                </div>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">{credential.description || 'No description'}</p>
                <p className="mt-1 font-mono text-xs text-zinc-500">{credential.username ?? 'no username'} / {credential.masked_secret}</p>
              </div>
              <button className="inline-flex items-center gap-2 rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50" type="button" onClick={() => handleDelete(credential)}>
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                Delete
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function TextInput({ label, value, placeholder, onChange }: { label: string; value: string; placeholder: string; onChange: (value: string) => void }) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm" placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Badge({ label }: { label: string }) {
  return <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">{label}</span>;
}

function splitCsv(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}
