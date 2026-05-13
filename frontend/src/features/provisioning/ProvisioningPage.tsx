import { useEffect, useMemo, useState } from 'react';

import { PageHeader } from '../../components/layout/PageHeader';
import { getApiErrorMessage } from '../../lib/api/client';
import { listPackageDefinitions } from '../packages/api/packagesApi';
import type { PackageDefinition } from '../packages/types/package';
import { listProfiles } from '../profiles/api/profilesApi';
import type { InfrastructureProfile } from '../profiles/types/profile';
import { createProvisioningRequest, listProxmoxTemplates, listProvisioningRequests } from './api/provisioningApi';
import type { CreateProvisioningPayload, ProxmoxTemplate, ProvisioningRequest } from './types/provisioning';

type FormState = {
  vm_name: string;
  target_node: string;
  template_id: string;
  new_vm_id: string;
  cpu_cores: string;
  memory_mb: string;
  disk_gb: string;
  network_bridge: string;
  environment: string;
  tags_text: string;
  description: string;
  start_on_boot: boolean;
  cloud_init_hostname: string;
  cloud_init_username: string;
  cloud_init_password: string;
  ssh_public_key: string;
  static_ip_cidr: string;
  gateway: string;
  dns_servers_text: string;
  bootstrap_profile_ids: string[];
  bootstrap_package_ids: string[];
};

const initialFormState: FormState = {
  vm_name: '',
  target_node: '',
  template_id: '',
  new_vm_id: '',
  cpu_cores: '2',
  memory_mb: '2048',
  disk_gb: '32',
  network_bridge: 'vmbr0',
  environment: 'lab',
  tags_text: 'provisioned',
  description: '',
  start_on_boot: false,
  cloud_init_hostname: '',
  cloud_init_username: 'ubuntu',
  cloud_init_password: '',
  ssh_public_key: '',
  static_ip_cidr: '',
  gateway: '',
  dns_servers_text: '1.1.1.1',
  bootstrap_profile_ids: [],
  bootstrap_package_ids: [],
};

export function ProvisioningPage() {
  const [templates, setTemplates] = useState<ProxmoxTemplate[]>([]);
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [requests, setRequests] = useState<ProvisioningRequest[]>([]);
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectedTemplate = useMemo(
    () => templates.find((template) => String(template.template_id) === formState.template_id) ?? null,
    [formState.template_id, templates],
  );

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const [nextTemplates, nextProfiles, nextPackages, nextRequests] = await Promise.all([
          listProxmoxTemplates(),
          listProfiles(),
          listPackageDefinitions(),
          listProvisioningRequests(),
        ]);
        setTemplates(nextTemplates);
        setProfiles(nextProfiles);
        setPackages(nextPackages);
        setRequests(nextRequests);
        const firstTemplate = nextTemplates[0];
        if (firstTemplate) {
          setFormState((current) => ({
            ...current,
            target_node: current.target_node || firstTemplate.node,
            template_id: current.template_id || String(firstTemplate.template_id),
          }));
        }
      } catch (caughtError) {
        setError(getApiErrorMessage(caughtError));
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, []);

  function updateField(name: keyof FormState, value: string | boolean | string[]) {
    setFormState((current) => ({ ...current, [name]: value }));
    setError(null);
    setSuccess(null);
  }

  async function handleSubmit() {
    const payload = toPayload(formState, selectedTemplate);
    if (!payload) {
      setError('Fill in VM name, VMID, template, static IP/CIDR, gateway, and cloud-init hostname.');
      return;
    }

    const confirmed = window.confirm(`Provision ${payload.vm_name} from template ${payload.template_id}?`);
    if (!confirmed) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await createProvisioningRequest(payload);
      setRequests((current) => [created, ...current]);
      setSuccess(`Provisioning finished with status ${created.status}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="VM Provisioning"
        description="Template-based Proxmox provisioning with cloud-init, static IPs, inventory registration, and bootstrap workflows."
      />

      {error ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</p> : null}
      {success ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">{success}</p> : null}

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-zinc-950">Provision VM</h3>
        {isLoading ? <div className="mt-4 h-40 animate-pulse rounded-md bg-zinc-100" /> : null}
        {!isLoading ? (
          <>
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <TextInput label="VM name" name="vm_name" value={formState.vm_name} onChange={updateField} />
              <TextInput label="Cloud hostname" name="cloud_init_hostname" value={formState.cloud_init_hostname} onChange={updateField} />
              <TextInput label="New VMID" name="new_vm_id" type="number" value={formState.new_vm_id} onChange={updateField} />
              <label className="text-sm font-medium text-zinc-700">
                Template
                <select
                  className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
                  value={formState.template_id}
                  onChange={(event) => {
                    const template = templates.find((item) => String(item.template_id) === event.target.value);
                    updateField('template_id', event.target.value);
                    if (template) updateField('target_node', template.node);
                  }}
                >
                  {templates.map((template) => (
                    <option key={`${template.node}-${template.template_id}`} value={template.template_id}>
                      {template.name} ({template.template_id})
                    </option>
                  ))}
                </select>
              </label>
              <TextInput label="Target node" name="target_node" value={formState.target_node} onChange={updateField} />
              <TextInput label="Network bridge" name="network_bridge" value={formState.network_bridge} onChange={updateField} />
              <TextInput label="CPU cores" name="cpu_cores" type="number" value={formState.cpu_cores} onChange={updateField} />
              <TextInput label="RAM MB" name="memory_mb" type="number" value={formState.memory_mb} onChange={updateField} />
              <TextInput label="Disk GB" name="disk_gb" type="number" value={formState.disk_gb} onChange={updateField} />
              <TextInput label="Static IP/CIDR" name="static_ip_cidr" value={formState.static_ip_cidr} onChange={updateField} />
              <TextInput label="Gateway" name="gateway" value={formState.gateway} onChange={updateField} />
              <TextInput label="DNS servers" name="dns_servers_text" value={formState.dns_servers_text} onChange={updateField} />
              <TextInput label="Cloud-init user" name="cloud_init_username" value={formState.cloud_init_username} onChange={updateField} />
              <TextInput label="Cloud-init password" name="cloud_init_password" type="password" value={formState.cloud_init_password} onChange={updateField} />
              <TextInput label="Environment" name="environment" value={formState.environment} onChange={updateField} />
              <TextInput label="Tags" name="tags_text" value={formState.tags_text} onChange={updateField} />
              <TextInput label="Description" name="description" value={formState.description} onChange={updateField} />
              <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
                <input
                  checked={formState.start_on_boot}
                  type="checkbox"
                  onChange={(event) => updateField('start_on_boot', event.target.checked)}
                />
                Start on boot
              </label>
              <label className="text-sm font-medium text-zinc-700 xl:col-span-3">
                SSH public key
                <textarea
                  className="mt-1 min-h-20 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 font-mono text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
                  value={formState.ssh_public_key}
                  onChange={(event) => updateField('ssh_public_key', event.target.value)}
                />
              </label>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <MultiSelect
                label="Bootstrap profiles"
                options={profiles.map((profile) => ({ label: profile.name, value: profile.id }))}
                value={formState.bootstrap_profile_ids}
                onChange={(value) => updateField('bootstrap_profile_ids', value)}
              />
              <MultiSelect
                label="Bootstrap packages"
                options={packages.map((pkg) => ({ label: pkg.name, value: pkg.id }))}
                value={formState.bootstrap_package_ids}
                onChange={(value) => updateField('bootstrap_package_ids', value)}
              />
            </div>

            <div className="mt-5 flex justify-end">
              <button
                className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
                disabled={isSubmitting}
                type="button"
                onClick={handleSubmit}
              >
                {isSubmitting ? 'Provisioning' : 'Provision VM'}
              </button>
            </div>
          </>
        ) : null}
      </section>

      <ProvisioningHistory requests={requests} />
    </div>
  );
}

function TextInput({
  label,
  name,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  name: keyof FormState;
  value: string;
  type?: string;
  onChange: (name: keyof FormState, value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <input
        className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
        type={type}
        value={value}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </label>
  );
}

function MultiSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Array<{ label: string; value: string }>;
  value: string[];
  onChange: (value: string[]) => void;
}) {
  return (
    <label className="text-sm font-medium text-zinc-700">
      {label}
      <select
        multiple
        className="mt-1 min-h-32 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
        value={value}
        onChange={(event) =>
          onChange(Array.from(event.target.selectedOptions).map((option) => option.value))
        }
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ProvisioningHistory({ requests }: { requests: ProvisioningRequest[] }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">Provisioning history</h3>
        <p className="mt-1 text-sm text-zinc-500">{requests.length} requests tracked.</p>
      </div>
      <div className="grid gap-3 p-4">
        {requests.map((request) => (
          <article key={request.id} className="rounded-lg border border-zinc-200 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h4 className="font-semibold text-zinc-950">{request.vm_name}</h4>
                <p className="mt-1 text-sm text-zinc-500">
                  VMID {request.new_vm_id} on {request.target_node} - {request.static_ip_cidr}
                </p>
              </div>
              <span className="inline-flex w-fit rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-700 ring-1 ring-zinc-200">
                {request.status}
              </span>
            </div>
            {request.error_message ? <p className="mt-3 text-sm text-rose-700">{request.error_message}</p> : null}
            <p className="mt-3 text-xs text-zinc-500">
              Tasks: {request.proxmox_task_ids.length} | Bootstrap jobs: {request.bootstrap_job_ids.length}
            </p>
          </article>
        ))}
        {requests.length === 0 ? <p className="text-sm text-zinc-500">No provisioning requests yet.</p> : null}
      </div>
    </section>
  );
}

function toPayload(formState: FormState, selectedTemplate: ProxmoxTemplate | null): CreateProvisioningPayload | null {
  if (!formState.vm_name || !formState.cloud_init_hostname || !formState.new_vm_id || !formState.template_id || !formState.static_ip_cidr || !formState.gateway) {
    return null;
  }

  return {
    vm_name: formState.vm_name.trim(),
    target_node: formState.target_node || selectedTemplate?.node || '',
    template_id: Number(formState.template_id),
    new_vm_id: Number(formState.new_vm_id),
    cpu_cores: Number(formState.cpu_cores),
    memory_mb: Number(formState.memory_mb),
    disk_gb: Number(formState.disk_gb),
    network_bridge: formState.network_bridge.trim(),
    environment: formState.environment.trim(),
    tags: splitCsv(formState.tags_text),
    description: formState.description.trim() || null,
    start_on_boot: formState.start_on_boot,
    cloud_init_hostname: formState.cloud_init_hostname.trim(),
    cloud_init_username: formState.cloud_init_username.trim(),
    cloud_init_password: formState.cloud_init_password.trim() || null,
    ssh_public_key: formState.ssh_public_key.trim() || null,
    static_ip_cidr: formState.static_ip_cidr.trim(),
    gateway: formState.gateway.trim(),
    dns_servers: splitCsv(formState.dns_servers_text),
    bootstrap_profile_ids: formState.bootstrap_profile_ids,
    bootstrap_package_ids: formState.bootstrap_package_ids,
  };
}

function splitCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}
