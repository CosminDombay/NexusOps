import { useEffect, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import { listCredentials } from '../../credentials/api/credentialsApi';
import type { Credential } from '../../credentials/types/credential';
import type { Server, UpdateServerPayload } from '../types/server';
import { environmentOptions, sshAuthMethodOptions } from '../utils/options';

type EditServerModalProps = {
  server: Server;
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: UpdateServerPayload) => Promise<void>;
  isSaving: boolean;
  error: string | null;
};

export function EditServerModal({
  server,
  isOpen,
  onClose,
  onSave,
  isSaving,
  error,
}: EditServerModalProps) {
  const [formData, setFormData] = useState<UpdateServerPayload>({
    hostname: server.hostname,
    ip_address: server.ip_address,
    operating_system: server.operating_system,
    ssh_port: server.ssh_port,
    ssh_username: server.ssh_username,
    ssh_auth_method: server.ssh_auth_method,
    credential_id: server.credential_id,
    environment: server.environment,
    provider: server.provider,
    tags: server.tags,
    lifecycle_state: server.lifecycle_state,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [credentials, setCredentials] = useState<Credential[]>([]);

  useEffect(() => {
    if (isOpen) {
      listCredentials().then(setCredentials).catch(() => setCredentials([]));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  function handleInputChange(field: keyof UpdateServerPayload, value: unknown) {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
    // Clear field-specific error when user starts editing
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  }

  function validateForm(): boolean {
    const newErrors: Record<string, string> = {};

    if (!formData.hostname?.trim()) {
      newErrors.hostname = 'Hostname is required';
    }
    if (!formData.ip_address?.trim()) {
      newErrors.ip_address = 'IP address is required';
    }
    if (!formData.ssh_username?.trim()) {
      newErrors.ssh_username = 'SSH username is required';
    }
    if (!formData.ssh_port || formData.ssh_port < 1 || formData.ssh_port > 65535) {
      newErrors.ssh_port = 'SSH port must be between 1-65535';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function handleSave(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      await onSave(formData);
      onClose();
    } catch {
      // Error is handled by parent component
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative w-full max-w-lg rounded-lg bg-white shadow-xl">
        {/* Header */}
        <div className="border-b border-zinc-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-950">Edit server</h2>
            <button
              type="button"
              onClick={onClose}
              className="text-zinc-400 transition hover:text-zinc-600"
              disabled={isSaving}
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Body */}
        <form id="edit-server-form" onSubmit={handleSave} className="space-y-4 px-6 py-4">
          {error && (
            <div className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
              {error}
            </div>
          )}

          {/* Hostname */}
          <div>
            <label className="block text-sm font-medium text-zinc-700">Hostname</label>
            <input
              type="text"
              value={formData.hostname || ''}
              onChange={(e) => handleInputChange('hostname', e.target.value)}
              disabled={isSaving}
              className={`mt-1 w-full rounded-md border px-3 py-2 text-sm transition focus:outline-none focus:ring-2 focus:ring-zinc-500 ${
                errors.hostname
                  ? 'border-rose-300 bg-rose-50'
                  : 'border-zinc-300 bg-white'
              }`}
            />
            {errors.hostname && (
              <p className="mt-1 text-xs text-rose-600">{errors.hostname}</p>
            )}
          </div>

          {/* IP Address */}
          <div>
            <label className="block text-sm font-medium text-zinc-700">IP address</label>
            <input
              type="text"
              value={formData.ip_address || ''}
              onChange={(e) => handleInputChange('ip_address', e.target.value)}
              disabled={isSaving}
              className={`mt-1 w-full rounded-md border px-3 py-2 text-sm transition focus:outline-none focus:ring-2 focus:ring-zinc-500 ${
                errors.ip_address
                  ? 'border-rose-300 bg-rose-50'
                  : 'border-zinc-300 bg-white'
              }`}
            />
            {errors.ip_address && (
              <p className="mt-1 text-xs text-rose-600">{errors.ip_address}</p>
            )}
          </div>

          {/* Operating System */}
          <div>
            <label className="block text-sm font-medium text-zinc-700">Operating system</label>
            <input
              type="text"
              value={formData.operating_system || ''}
              onChange={(e) => handleInputChange('operating_system', e.target.value)}
              disabled={isSaving}
              placeholder="e.g., Ubuntu 22.04 LTS"
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm transition focus:outline-none focus:ring-2 focus:ring-zinc-500"
            />
          </div>

          {/* SSH Configuration */}
          <div className="space-y-3 rounded-md border border-zinc-200 bg-zinc-50 p-3">
            <h3 className="text-sm font-medium text-zinc-900">SSH Configuration</h3>

            {/* SSH Username */}
            <div>
              <label className="block text-xs font-medium text-zinc-700">Username</label>
              <input
                type="text"
                value={formData.ssh_username || ''}
                onChange={(e) => handleInputChange('ssh_username', e.target.value)}
                disabled={isSaving}
                className={`mt-1 w-full rounded-md border px-3 py-2 text-xs transition focus:outline-none focus:ring-2 focus:ring-zinc-500 ${
                  errors.ssh_username
                    ? 'border-rose-300 bg-rose-50'
                    : 'border-zinc-300 bg-white'
                }`}
              />
              {errors.ssh_username && (
                <p className="mt-1 text-xs text-rose-600">{errors.ssh_username}</p>
              )}
            </div>

            {/* SSH Port */}
            <div>
              <label className="block text-xs font-medium text-zinc-700">Port</label>
              <input
                type="number"
                value={formData.ssh_port || 22}
                onChange={(e) => handleInputChange('ssh_port', parseInt(e.target.value))}
                disabled={isSaving}
                min="1"
                max="65535"
                className={`mt-1 w-full rounded-md border px-3 py-2 text-xs transition focus:outline-none focus:ring-2 focus:ring-zinc-500 ${
                  errors.ssh_port
                    ? 'border-rose-300 bg-rose-50'
                    : 'border-zinc-300 bg-white'
                }`}
              />
              {errors.ssh_port && (
                <p className="mt-1 text-xs text-rose-600">{errors.ssh_port}</p>
              )}
            </div>

            {/* SSH Auth Method */}
            <div>
              <label className="block text-xs font-medium text-zinc-700">Shared credential</label>
              <select
                value={formData.credential_id || ''}
                onChange={(e) => handleInputChange('credential_id', e.target.value || null)}
                disabled={isSaving}
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-xs transition focus:outline-none focus:ring-2 focus:ring-zinc-500"
              >
                <option value="">Inline SSH metadata</option>
                {credentials.map((credential) => (
                  <option key={credential.id} value={credential.id}>
                    {credential.name}{credential.username ? ` (${credential.username})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-700">Auth method</label>
              <select
                value={formData.ssh_auth_method || 'key'}
                onChange={(e) => handleInputChange('ssh_auth_method', e.target.value)}
                disabled={isSaving}
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-xs transition focus:outline-none focus:ring-2 focus:ring-zinc-500"
              >
                {sshAuthMethodOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Environment */}
          <div>
            <label className="block text-sm font-medium text-zinc-700">Environment</label>
            <select
              value={formData.environment || ''}
              onChange={(e) => handleInputChange('environment', e.target.value)}
              disabled={isSaving}
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm transition focus:outline-none focus:ring-2 focus:ring-zinc-500"
            >
              <option value="">Select environment</option>
              {environmentOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Tags */}
          <div>
            <label className="block text-sm font-medium text-zinc-700">Tags</label>
            <input
              type="text"
              value={(formData.tags || []).join(', ')}
              onChange={(e) =>
                handleInputChange(
                  'tags',
                  e.target.value
                    .split(',')
                    .map((t) => t.trim())
                    .filter(Boolean),
                )
              }
              disabled={isSaving}
              placeholder="Comma-separated tags"
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm transition focus:outline-none focus:ring-2 focus:ring-zinc-500"
            />
          </div>
        </form>

        {/* Footer */}
        <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-3">
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:bg-zinc-100 disabled:text-zinc-400"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="edit-server-form"
              disabled={isSaving}
              className="rounded-md border border-zinc-900 bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:border-zinc-300 disabled:bg-zinc-100 disabled:text-zinc-400"
            >
              {isSaving ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
