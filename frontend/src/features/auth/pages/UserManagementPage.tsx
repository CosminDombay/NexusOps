import { useEffect, useState } from 'react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../../lib/api/client';
import { createUser, listUsers, resetUserPassword, updateUser, type CreateUserPayload } from '../api/usersApi';
import type { AuthUser, UserRole } from '../types/auth';

const initialForm: CreateUserPayload = {
  email: '',
  username: '',
  password: '',
  role: 'viewer',
  is_active: true,
  is_superuser: false,
};

export function UserManagementPage() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [form, setForm] = useState<CreateUserPayload>(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      setUsers(await listUsers());
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  async function submit() {
    if (!form.username || !form.email || !form.password) {
      setError('Username, email, and initial password are required.');
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await createUser(form);
      setUsers((current) => [created, ...current]);
      setForm(initialForm);
      setSuccess(`Created ${created.username}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function patchUser(user: AuthUser, patch: Partial<AuthUser>) {
    setIsWorking(true);
    setError(null);
    try {
      const updated = await updateUser(user.id, {
        username: patch.username,
        email: patch.email,
        role: patch.role,
        is_active: patch.is_active,
        is_superuser: patch.is_superuser,
      });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function resetPassword(user: AuthUser) {
    const password = window.prompt(`New password for ${user.username}`);
    if (!password) {
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      const updated = await resetUserPassword(user.id, password);
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSuccess(`Password reset for ${user.username}.`);
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
      <PageHeader title="Users & RBAC" description="Admin-only user lifecycle, role assignment, and account activation controls." />

      {error ? <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
      {success ? <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p> : null}

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Create user</h3>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <TextInput label="Username" value={form.username} onChange={(username) => setForm({ ...form, username })} />
          <TextInput label="Email" value={form.email} onChange={(email) => setForm({ ...form, email })} />
          <TextInput label="Initial password" type="password" value={form.password} onChange={(password) => setForm({ ...form, password })} />
          <RoleSelect value={form.role} onChange={(role) => setForm({ ...form, role })} />
          <Toggle label="Active" checked={form.is_active} onChange={(is_active) => setForm({ ...form, is_active })} />
          <Toggle label="Superuser" checked={form.is_superuser} onChange={(is_superuser) => setForm({ ...form, is_superuser })} />
        </div>
        <div className="mt-4 flex justify-end">
          <button className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:bg-zinc-300" disabled={isWorking} type="button" onClick={() => void submit()}>
            Create user
          </button>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h3 className="text-base font-semibold text-zinc-950">User accounts</h3>
          <p className="mt-1 text-sm text-zinc-500">{users.length} account(s).</p>
        </div>
        {isLoading ? <div className="m-5 h-24 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-50">
                <tr>
                  {['User', 'Role', 'State', 'Last login', 'Actions'].map((heading) => (
                    <th key={heading} className="px-5 py-3 text-left text-xs font-semibold uppercase text-zinc-500">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="px-5 py-4">
                      <div className="font-semibold text-zinc-950">{user.username}</div>
                      <div className="text-xs text-zinc-500">{user.email}</div>
                    </td>
                    <td className="px-5 py-4">
                      <select className="rounded-md border border-zinc-300 px-2 py-1" value={user.role} onChange={(event) => void patchUser(user, { role: event.target.value as UserRole })}>
                        <option value="viewer">viewer</option>
                        <option value="operator">operator</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td className="px-5 py-4">
                      <button className="rounded-full border border-zinc-300 px-2.5 py-1 text-xs font-semibold" type="button" onClick={() => void patchUser(user, { is_active: !user.is_active })}>
                        {user.is_active ? 'active' : 'inactive'}
                      </button>
                      {user.is_superuser ? <span className="ml-2 rounded-full bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700 ring-1 ring-sky-200">superuser</span> : null}
                    </td>
                    <td className="px-5 py-4 text-zinc-500">{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}</td>
                    <td className="px-5 py-4">
                      <button className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700" disabled={isWorking} type="button" onClick={() => void resetPassword(user)}>
                        Reset password
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function TextInput({ label, value, type = 'text', onChange }: { label: string; value: string; type?: string; onChange: (value: string) => void }) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function RoleSelect({ value, onChange }: { value: UserRole; onChange: (value: UserRole) => void }) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      Role
      <select className="mt-1 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value as UserRole)}>
        <option value="viewer">viewer</option>
        <option value="operator">operator</option>
        <option value="admin">admin</option>
      </select>
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 self-end text-sm font-medium text-zinc-700">
      <input checked={checked} type="checkbox" onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}
