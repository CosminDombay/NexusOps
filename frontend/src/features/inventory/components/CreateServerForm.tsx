import { AlertCircle, Loader2, Plus } from 'lucide-react';
import { FormEvent, useMemo, useState } from 'react';

import type { CreateServerPayload, ServerEnvironment, ServerSshAuthMethod } from '../types/server';
import { environmentOptions, sshAuthMethodOptions } from '../utils/options';

type FormState = {
  hostname: string;
  ip_address: string;
  operating_system: string;
  environment: ServerEnvironment;
  provider: string;
  ssh_port: string;
  ssh_username: string;
  ssh_auth_method: ServerSshAuthMethod;
  ssh_password: string;
  ssh_private_key_path: string;
};

type CreateServerFormProps = {
  isSubmitting: boolean;
  apiError: string | null;
  onSubmit: (payload: CreateServerPayload) => Promise<boolean>;
  onFieldChange: () => void;
};

const initialFormState: FormState = {
  hostname: '',
  ip_address: '',
  operating_system: '',
  environment: 'development',
  provider: '',
  ssh_port: '22',
  ssh_username: '',
  ssh_auth_method: 'key',
  ssh_password: '',
  ssh_private_key_path: '',
};

const textFields: Array<{
  name: keyof Pick<
    FormState,
    'hostname' | 'ip_address' | 'operating_system' | 'provider' | 'ssh_port' | 'ssh_username'
  >;
  label: string;
  placeholder: string;
  type?: string;
}> = [
  { name: 'hostname', label: 'Hostname', placeholder: 'app-01.internal' },
  { name: 'ip_address', label: 'IP address', placeholder: '10.0.0.10' },
  { name: 'operating_system', label: 'Operating system', placeholder: 'Ubuntu 24.04 LTS' },
  { name: 'provider', label: 'Provider', placeholder: 'proxmox' },
  { name: 'ssh_port', label: 'SSH port', placeholder: '22', type: 'number' },
  { name: 'ssh_username', label: 'SSH username', placeholder: 'ubuntu' },
];

export function CreateServerForm({ isSubmitting, apiError, onSubmit, onFieldChange }: CreateServerFormProps) {
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [validationError, setValidationError] = useState<string | null>(null);

  const requiredFields = useMemo(
    () => textFields.filter((field) => field.name !== 'ssh_port').map((field) => field.name),
    [],
  );

  function updateField(name: keyof FormState, value: string) {
    setFormState((current) => ({ ...current, [name]: value }));
    setValidationError(null);
    onFieldChange();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const missingField = requiredFields.find((fieldName) => !formState[fieldName].trim());
    if (missingField) {
      setValidationError('Fill in all required server fields before creating the record.');
      return;
    }

    const sshPort = Number(formState.ssh_port);
    if (!Number.isInteger(sshPort) || sshPort < 1 || sshPort > 65535) {
      setValidationError('SSH port must be a whole number between 1 and 65535.');
      return;
    }

    if (formState.ssh_auth_method === 'password' && !formState.ssh_password.trim()) {
      setValidationError('SSH password is required when password authentication is selected.');
      return;
    }

    const created = await onSubmit({
      hostname: formState.hostname.trim(),
      ip_address: formState.ip_address.trim(),
      operating_system: formState.operating_system.trim(),
      environment: formState.environment,
      provider: formState.provider.trim(),
      ssh_port: sshPort,
      ssh_username: formState.ssh_username.trim(),
      ssh_auth_method: formState.ssh_auth_method,
      ssh_password:
        formState.ssh_auth_method === 'password' ? formState.ssh_password.trim() : null,
      ssh_private_key_path:
        formState.ssh_auth_method === 'key' && formState.ssh_private_key_path.trim()
          ? formState.ssh_private_key_path.trim()
          : null,
    });

    if (created) {
      setFormState(initialFormState);
    }
  }

  const visibleError = validationError ?? apiError;

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-zinc-950">Register server</h3>
          <p className="mt-1 text-sm text-zinc-500">Add connection metadata for an existing Linux host.</p>
        </div>
      </div>

      {visibleError ? (
        <div className="mt-4 flex gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{visibleError}</span>
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {textFields.map((field) => (
          <label key={field.name} className="text-sm font-medium text-zinc-700">
            {field.label}
            <input
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
              min={field.type === 'number' ? 1 : undefined}
              max={field.type === 'number' ? 65535 : undefined}
              placeholder={field.placeholder}
              type={field.type ?? 'text'}
              value={formState[field.name]}
              onChange={(event) => updateField(field.name, event.target.value)}
            />
          </label>
        ))}

        <label className="text-sm font-medium text-zinc-700">
          Environment
          <select
            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
            value={formState.environment}
            onChange={(event) => updateField('environment', event.target.value as ServerEnvironment)}
          >
            {environmentOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm font-medium text-zinc-700">
          SSH authentication
          <select
            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
            value={formState.ssh_auth_method}
            onChange={(event) => updateField('ssh_auth_method', event.target.value as ServerSshAuthMethod)}
          >
            {sshAuthMethodOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        {formState.ssh_auth_method === 'key' ? (
          <label className="text-sm font-medium text-zinc-700 xl:col-span-2">
            SSH private key path
            <input
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
              placeholder="Optional, falls back to configured key or SSH agent"
              type="text"
              value={formState.ssh_private_key_path}
              onChange={(event) => updateField('ssh_private_key_path', event.target.value)}
            />
          </label>
        ) : (
          <label className="text-sm font-medium text-zinc-700 xl:col-span-2">
            SSH password
            <input
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
              placeholder="Temporary bootstrap password"
              type="password"
              value={formState.ssh_password}
              onChange={(event) => updateField('ssh_password', event.target.value)}
            />
          </label>
        )}
      </div>

      <div className="mt-5 flex justify-end">
        <button
          className="inline-flex items-center gap-2 rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-400"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Plus className="h-4 w-4" aria-hidden="true" />}
          Create server
        </button>
      </div>
    </form>
  );
}
