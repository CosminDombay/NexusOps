import { useEffect, useMemo, useState } from 'react';

import { ContextDrawer } from '../../components/ContextDrawer';
import { PageHeader } from '../../components/layout/PageHeader';
import { CollapsibleSection, PageActionButton } from '../../components/operations/OperationalComponents';
import { getApiErrorMessage } from '../../lib/api/client';
import { listPackageDefinitions } from '../packages/api/packagesApi';
import type { PackageDefinition } from '../packages/types/package';
import { listProfiles } from '../profiles/api/profilesApi';
import type { InfrastructureProfile } from '../profiles/types/profile';
import {
  createProvisioningBlueprint,
  createProvisioningBatch,
  createProvisioningRequest,
  deleteProvisioningBlueprint,
  deleteProvisioningRequest,
  listProxmoxStorage,
  listProxmoxTemplates,
  listProvisioningBatches,
  listProvisioningBlueprints,
  listProvisioningRequests,
  updateProvisioningBlueprint,
} from './api/provisioningApi';
import type {
  CreateProvisioningPayload,
  ProvisioningBatch,
  ProxmoxStorage,
  ProxmoxTemplate,
  ProvisioningBlueprint,
  ProvisioningRequest,
} from './types/provisioning';

type FormState = {
  vm_name: string;
  target_node: string;
  template_id: string;
  new_vm_id: string;
  cpu_cores: string;
  memory_mb: string;
  disk_gb: string;
  additional_disks: Array<{ size_gb: string; storage: string; bus: 'scsi' | 'virtio' | 'sata' }>;
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

type BatchFormState = {
  name: string;
  blueprint_id: string;
  count: string;
  vm_name_pattern: string;
  hostname_pattern: string;
  starting_vm_id: string;
  starting_ip_cidr: string;
  cloud_init_password: string;
  description: string;
};

const initialBatchFormState: BatchFormState = {
  name: '',
  blueprint_id: '',
  count: '2',
  vm_name_pattern: 'vm-{index}',
  hostname_pattern: 'vm-{index}',
  starting_vm_id: '',
  starting_ip_cidr: '',
  cloud_init_password: '',
  description: '',
};

const initialFormState: FormState = {
  vm_name: '',
  target_node: '',
  template_id: '',
  new_vm_id: '',
  cpu_cores: '2',
  memory_mb: '2048',
  disk_gb: '32',
  additional_disks: [],
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
  const [storageOptions, setStorageOptions] = useState<ProxmoxStorage[]>([]);
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [requests, setRequests] = useState<ProvisioningRequest[]>([]);
  const [batches, setBatches] = useState<ProvisioningBatch[]>([]);
  const [blueprints, setBlueprints] = useState<ProvisioningBlueprint[]>([]);
  const [provisioningKind, setProvisioningKind] = useState<'qemu' | 'lxc'>('qemu');
  const [selectedBlueprintId, setSelectedBlueprintId] = useState('');
  const [blueprintName, setBlueprintName] = useState('');
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [batchFormState, setBatchFormState] = useState<BatchFormState>(initialBatchFormState);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{
    tone: 'success' | 'danger' | 'warning';
    message: string;
  } | null>(null);
  const [isBlueprintOpen, setIsBlueprintOpen] = useState(false);
  const [isBatchOpen, setIsBatchOpen] = useState(false);

  const filteredTemplates = useMemo(
    () => templates.filter((template) => (provisioningKind === 'lxc' ? template.type === 'lxc' : template.type !== 'lxc')),
    [provisioningKind, templates],
  );

  const selectedTemplate = useMemo(
    () =>
      filteredTemplates.find((template) => String(template.template_id) === formState.template_id) ??
      null,
    [filteredTemplates, formState.template_id],
  );

  const diskStorageOptions = useMemo(
    () =>
      storageOptions.filter(
        (storage) =>
          (!storage.node || !formState.target_node || storage.node === formState.target_node) &&
          (storage.content.length === 0 || storage.content.includes('images')) &&
          storage.storage !== 'unknown',
      ),
    [formState.target_node, storageOptions],
  );

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const [
          nextTemplates,
          nextProfiles,
          nextPackages,
          nextRequests,
          nextBlueprints,
          nextBatches,
        ] = await Promise.all([
          listProxmoxTemplates(),
          listProfiles(),
          listPackageDefinitions(),
          listProvisioningRequests(),
          listProvisioningBlueprints(),
          listProvisioningBatches(),
        ]);
        const nodeNames = Array.from(
          new Set(nextTemplates.map((template) => template.node).filter(Boolean)),
        );
        const nextStorage = (
          await Promise.all(
            nodeNames.length
              ? nodeNames.map((nodeName) => listProxmoxStorage(nodeName))
              : [listProxmoxStorage()],
          )
        ).flat();
        setTemplates(nextTemplates);
        setStorageOptions(nextStorage);
        setProfiles(nextProfiles);
        setPackages(nextPackages);
        setRequests(nextRequests);
        setBlueprints(nextBlueprints);
        setBatches(nextBatches);
        const firstTemplate = nextTemplates[0];
        if (firstTemplate) {
          setProvisioningKind(firstTemplate.type === 'lxc' ? 'lxc' : 'qemu');
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

  function updateField(name: keyof FormState, value: FormState[keyof FormState]) {
    setFormState((current) => ({ ...current, [name]: value }));
    setError(null);
    setNotice(null);
  }

  function updateBatchField(name: keyof BatchFormState, value: string) {
    setBatchFormState((current) => ({ ...current, [name]: value }));
    setError(null);
    setNotice(null);
  }

  function updateAdditionalDisk(
    index: number,
    patch: Partial<FormState['additional_disks'][number]>,
  ) {
    setFormState((current) => ({
      ...current,
      additional_disks: current.additional_disks.map((disk, diskIndex) =>
        diskIndex === index ? { ...disk, ...patch } : disk,
      ),
    }));
    setError(null);
    setNotice(null);
  }

  function selectProvisioningKind(kind: 'qemu' | 'lxc') {
    setProvisioningKind(kind);
    const nextTemplate = templates.find((template) =>
      kind === 'lxc' ? template.type === 'lxc' : template.type !== 'lxc',
    );
    setFormState((current) => ({
      ...current,
      template_id: nextTemplate ? String(nextTemplate.template_id) : '',
      target_node: nextTemplate?.node ?? current.target_node,
      cloud_init_username:
        kind === 'lxc' && current.cloud_init_username === 'ubuntu'
          ? 'root'
          : kind === 'qemu' && current.cloud_init_username === 'root'
            ? 'ubuntu'
            : current.cloud_init_username,
      tags_text: kind === 'lxc' ? ensureCsvValue(current.tags_text, 'lxc') : current.tags_text,
    }));
    setError(null);
    setNotice(null);
  }

  function applyBlueprint(blueprint: ProvisioningBlueprint) {
    setSelectedBlueprintId(blueprint.id);
    setBlueprintName(blueprint.name);
    setFormState((current) => ({
      ...current,
      target_node: blueprint.target_node,
      template_id: String(blueprint.template_id),
      cpu_cores: String(blueprint.cpu_cores),
      memory_mb: String(blueprint.memory_mb),
      disk_gb: String(blueprint.disk_gb),
      additional_disks: blueprint.additional_disks.map((disk) => ({
        size_gb: String(disk.size_gb),
        storage: disk.storage,
        bus: disk.bus,
      })),
      network_bridge: blueprint.network_bridge,
      environment: blueprint.environment,
      tags_text: blueprint.tags.join(', '),
      description: blueprint.description ?? '',
      start_on_boot: blueprint.start_on_boot,
      cloud_init_username: blueprint.cloud_init_username,
      ssh_public_key: blueprint.ssh_public_key ?? '',
      gateway: blueprint.gateway,
      dns_servers_text: blueprint.dns_servers.join(', '),
      bootstrap_profile_ids: blueprint.bootstrap_profile_ids,
      bootstrap_package_ids: blueprint.bootstrap_package_ids,
    }));
    const slug = blueprint.name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    setBatchFormState((current) => ({
      ...current,
      blueprint_id: blueprint.id,
      name: current.name || `${blueprint.name} batch`,
      vm_name_pattern:
        current.vm_name_pattern === initialBatchFormState.vm_name_pattern
          ? `${slug}-{index}`
          : current.vm_name_pattern,
      hostname_pattern:
        current.hostname_pattern === initialBatchFormState.hostname_pattern
          ? `${slug}-{index}`
          : current.hostname_pattern,
      description: current.description || blueprint.description || '',
    }));
    setError(null);
    setNotice({ tone: 'success', message: `Loaded blueprint ${blueprint.name}.` });
  }

  async function handleSaveBlueprint() {
    const payload = toBlueprintPayload(formState, blueprintName.trim());
    if (!payload) {
      setError('Blueprint name, template, target node, and gateway are required.');
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createProvisioningBlueprint(payload);
      setBlueprints((current) =>
        [...current, created].sort((left, right) => left.name.localeCompare(right.name)),
      );
      setSelectedBlueprintId(created.id);
      setNotice({ tone: 'success', message: `Saved blueprint ${created.name}.` });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUpdateBlueprint() {
    const blueprint = blueprints.find((item) => item.id === selectedBlueprintId);
    const payload = toBlueprintPayload(formState, blueprintName.trim() || blueprint?.name || '');
    if (!blueprint || !payload) {
      setError('Select a blueprint and fill the required defaults before updating.');
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateProvisioningBlueprint(blueprint.id, payload);
      setBlueprints((current) =>
        current
          .map((item) => (item.id === updated.id ? updated : item))
          .sort((left, right) => left.name.localeCompare(right.name)),
      );
      setBlueprintName(updated.name);
      setNotice({ tone: 'success', message: `Updated blueprint ${updated.name}.` });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCloneBlueprint() {
    const blueprint = blueprints.find((item) => item.id === selectedBlueprintId);
    if (!blueprint) {
      return;
    }
    const cloneName = window.prompt('Clone blueprint as', `${blueprint.name} Copy`);
    if (!cloneName?.trim()) {
      return;
    }
    const payload = toBlueprintPayload(formState, cloneName.trim());
    if (!payload) {
      setError('Blueprint clone needs template, target node, and gateway defaults.');
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createProvisioningBlueprint(payload);
      setBlueprints((current) =>
        [...current, created].sort((left, right) => left.name.localeCompare(right.name)),
      );
      setSelectedBlueprintId(created.id);
      setBlueprintName(created.name);
      setNotice({ tone: 'success', message: `Cloned blueprint ${created.name}.` });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteBlueprint() {
    const blueprint = blueprints.find((item) => item.id === selectedBlueprintId);
    if (!blueprint) {
      return;
    }
    const confirmed = window.confirm(`Delete blueprint ${blueprint.name}?`);
    if (!confirmed) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await deleteProvisioningBlueprint(blueprint.id);
      setBlueprints((current) => current.filter((item) => item.id !== blueprint.id));
      setSelectedBlueprintId('');
      setNotice({ tone: 'success', message: `Deleted blueprint ${blueprint.name}.` });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSubmit() {
    const payload = toPayload(formState, selectedTemplate);
    if (!payload) {
      setError(
        'Fill in VM name, VMID, template, static IP/CIDR, gateway, and cloud-init hostname.',
      );
      return;
    }

    const confirmed = window.confirm(
      `Provision ${payload.vm_name} from template ${payload.template_id}?`,
    );
    if (!confirmed) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createProvisioningRequest(payload);
      setRequests((current) => [created, ...current]);
      setNotice({
        tone: created.status === 'completed' ? 'success' : 'danger',
        message: `Provisioning finished with status ${created.status}.`,
      });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleBatchSubmit() {
    const payload = toBatchPayload(batchFormState);
    if (!payload) {
      setError('Select a blueprint, count, name pattern, starting VMID, and starting IP/CIDR.');
      return;
    }

    const confirmed = window.confirm(`Provision ${payload.count} VMs from this blueprint?`);
    if (!confirmed) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createProvisioningBatch(payload);
      setBatches((current) => [created, ...current]);
      setRequests((current) => [...created.requests, ...current]);
      setNotice({
        tone:
          created.status === 'completed'
            ? 'success'
            : created.status === 'partial_failed'
              ? 'warning'
              : 'danger',
        message: `Batch finished with status ${created.status}: ${created.completed_count}/${created.count} completed.`,
      });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteRequest(request: ProvisioningRequest) {
    const confirmed = window.confirm(
      `Delete provisioning history for ${request.vm_name}? This only removes the NexusOps request record; it does not delete the VM or inventory host.`,
    );
    if (!confirmed) {
      return;
    }
    setError(null);
    setNotice(null);
    try {
      await deleteProvisioningRequest(request.id);
      setRequests((current) => current.filter((item) => item.id !== request.id));
      setNotice({
        tone: 'success',
        message: `Deleted provisioning history for ${request.vm_name}.`,
      });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="VM Provisioning"
        description="Template-based Proxmox provisioning with cloud-init, static IPs, inventory registration, and bootstrap workflows."
        actions={
          <>
            <PageActionButton tone="secondary" onClick={() => setIsBlueprintOpen(true)}>
              Blueprint actions
            </PageActionButton>
            <PageActionButton tone="secondary" onClick={() => setIsBatchOpen(true)}>
              Provision batch
            </PageActionButton>
          </>
        }
      />

      {error ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error}
        </p>
      ) : null}
      {notice ? <Notice tone={notice.tone} message={notice.message} /> : null}

      <CollapsibleSection
        title="Provisioning blueprint"
        description="Load and maintain saved defaults without keeping blueprint controls expanded."
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <label className="flex-1 text-sm font-medium text-zinc-700">
            Provisioning blueprint
            <select
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
              value={selectedBlueprintId}
              onChange={(event) => {
                const blueprint = blueprints.find((item) => item.id === event.target.value);
                if (blueprint) {
                  applyBlueprint(blueprint);
                } else {
                  setSelectedBlueprintId('');
                }
              }}
            >
              <option value="">No blueprint selected</option>
              {blueprints.map((blueprint) => (
                <option key={blueprint.id} value={blueprint.id}>
                  {blueprint.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
            type="button"
            onClick={() => setIsBlueprintOpen(true)}
          >
            Save / edit blueprint
          </button>
        </div>
        <ContextDrawer
          description="Save the current wizard defaults, duplicate selected blueprints, or maintain blueprint records."
          isOpen={isBlueprintOpen}
          title="Blueprint Actions"
          width="lg"
          onClose={() => setIsBlueprintOpen(false)}
        >
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
            <label className="flex-1 text-sm font-medium text-zinc-700">
              Save current defaults as
              <input
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
                placeholder="Ubuntu Docker Host"
                value={blueprintName}
                onChange={(event) => setBlueprintName(event.target.value)}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
                disabled={isSubmitting}
                type="button"
                onClick={() => void handleSaveBlueprint()}
              >
                Save blueprint
              </button>
              <button
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
                disabled={!selectedBlueprintId || isSubmitting}
                type="button"
                onClick={() => void handleUpdateBlueprint()}
              >
                Update
              </button>
              <button
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
                disabled={!selectedBlueprintId || isSubmitting}
                type="button"
                onClick={() => void handleCloneBlueprint()}
              >
                Clone
              </button>
              <button
                className="rounded-md border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-50 disabled:opacity-50"
                disabled={!selectedBlueprintId || isSubmitting}
                type="button"
                onClick={() => void handleDeleteBlueprint()}
              >
                Delete
              </button>
            </div>
          </div>
        </ContextDrawer>
        <p className="mt-3 text-sm text-zinc-500">
          Blueprints keep the fixed provisioning shape: Proxmox template, sizing, disks, network,
          environment, and bootstrap profiles. VMID, hostname, and IP stay per-machine.
        </p>
      </CollapsibleSection>

      <CollapsibleSection
        title="Batch provisioning"
        description="Create multiple VMs from one blueprint using sequential VMIDs and IP addresses."
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-1">
            <h3 className="text-base font-semibold text-zinc-950">Batch provisioning</h3>
            <p className="text-sm text-zinc-500">
              Create multiple VMs from one blueprint using sequential VMIDs and IP addresses.
            </p>
          </div>
          <button
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50"
            type="button"
            onClick={() => setIsBatchOpen(true)}
          >
            Provision batch
          </button>
        </div>
        <ContextDrawer
          description="Create multiple VMs from one blueprint using sequential VMIDs and IP addresses."
          isOpen={isBatchOpen}
          title="Batch Provisioning"
          width="xl"
          onClose={() => setIsBatchOpen(false)}
        >
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <label className="text-sm font-medium text-zinc-700">
              Blueprint
              <select
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
                value={batchFormState.blueprint_id}
                onChange={(event) => updateBatchField('blueprint_id', event.target.value)}
              >
                <option value="">Select blueprint</option>
                {blueprints.map((blueprint) => (
                  <option key={blueprint.id} value={blueprint.id}>
                    {blueprint.name}
                  </option>
                ))}
              </select>
            </label>
            <BatchTextInput
              label="Batch name"
              name="name"
              value={batchFormState.name}
              onChange={updateBatchField}
            />
            <BatchTextInput
              label="Count"
              name="count"
              type="number"
              value={batchFormState.count}
              onChange={updateBatchField}
            />
            <BatchTextInput
              label="VM name pattern"
              name="vm_name_pattern"
              value={batchFormState.vm_name_pattern}
              onChange={updateBatchField}
            />
            <BatchTextInput
              label="Hostname pattern"
              name="hostname_pattern"
              value={batchFormState.hostname_pattern}
              onChange={updateBatchField}
            />
            <BatchTextInput
              label="Starting VMID"
              name="starting_vm_id"
              type="number"
              value={batchFormState.starting_vm_id}
              onChange={updateBatchField}
            />
            <BatchTextInput
              label="Starting IP/CIDR"
              name="starting_ip_cidr"
              value={batchFormState.starting_ip_cidr}
              onChange={updateBatchField}
            />
            <BatchTextInput
              label="Cloud-init password"
              name="cloud_init_password"
              type="password"
              value={batchFormState.cloud_init_password}
              onChange={updateBatchField}
            />
            <BatchTextInput
              label="Description"
              name="description"
              value={batchFormState.description}
              onChange={updateBatchField}
            />
          </div>
          <p className="mt-3 text-xs text-zinc-500">
            Patterns support <code>{'{index}'}</code> as zero-padded numbers like 001 and{' '}
            <code>{'{number}'}</code> as plain numbers.
          </p>
          <div className="mt-5 flex justify-end">
            <button
              className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
              disabled={isSubmitting}
              type="button"
              onClick={() => void handleBatchSubmit()}
            >
              {isSubmitting ? 'Provisioning batch' : 'Provision batch'}
            </button>
          </div>
        </ContextDrawer>
      </CollapsibleSection>

      <CollapsibleSection
        title={`Provision ${provisioningKind === 'lxc' ? 'LXC container' : 'VM'}`}
        description={
          provisioningKind === 'lxc'
            ? 'Create a Proxmox CT from a downloaded container template and register it as an LXC managed node.'
            : 'Clone a Proxmox VM template and register it as a VM managed node.'
        }
        defaultOpen
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <h3 className="text-base font-semibold text-zinc-950">
              Provision {provisioningKind === 'lxc' ? 'LXC container' : 'VM'}
            </h3>
            <p className="mt-1 text-sm text-zinc-500">
              {provisioningKind === 'lxc'
                ? 'Create a Proxmox CT from a downloaded container template and register it as an LXC managed node.'
                : 'Clone a Proxmox VM template and register it as a VM managed node.'}
            </p>
          </div>
          <div className="inline-flex rounded-md border border-zinc-300 bg-zinc-50 p-1">
            <button
              className={`rounded px-3 py-1.5 text-sm font-semibold transition ${
                provisioningKind === 'qemu'
                  ? 'bg-zinc-950 text-white shadow-sm'
                  : 'text-zinc-600 hover:text-zinc-950'
              }`}
              type="button"
              onClick={() => selectProvisioningKind('qemu')}
            >
              VM
            </button>
            <button
              className={`rounded px-3 py-1.5 text-sm font-semibold transition ${
                provisioningKind === 'lxc'
                  ? 'bg-cyan-500 text-zinc-950 shadow-sm'
                  : 'text-zinc-600 hover:text-zinc-950'
              }`}
              type="button"
              onClick={() => selectProvisioningKind('lxc')}
            >
              LXC
            </button>
          </div>
        </div>
        <>
          <WizardSteps
            steps={['Blueprint', provisioningKind === 'lxc' ? 'CT fields' : 'VM fields', provisioningKind === 'lxc' ? 'Container auth' : 'Cloud-init/auth', 'Bootstrap', 'Review', 'Run']}
            currentIndex={reviewCompleteness(formState, selectedBlueprintId)}
          />
          {isLoading ? <div className="mt-4 h-40 animate-pulse rounded-md bg-zinc-100" /> : null}
          {!isLoading ? (
            <>
              <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <TextInput
                  label={provisioningKind === 'lxc' ? 'Container name' : 'VM name'}
                  name="vm_name"
                  value={formState.vm_name}
                  onChange={updateField}
                />
                <TextInput
                  label={provisioningKind === 'lxc' ? 'Container hostname' : 'Cloud hostname'}
                  name="cloud_init_hostname"
                  value={formState.cloud_init_hostname}
                  onChange={updateField}
                />
                <TextInput
                  label={provisioningKind === 'lxc' ? 'New CTID' : 'New VMID'}
                  name="new_vm_id"
                  type="number"
                  value={formState.new_vm_id}
                  onChange={updateField}
                />
                <label className="text-sm font-medium text-zinc-700">
                  Template
                  <select
                    className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950 shadow-sm outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10"
                    value={formState.template_id}
                    onChange={(event) => {
                      const template = filteredTemplates.find(
                        (item) => String(item.template_id) === event.target.value,
                      );
                      updateField('template_id', event.target.value);
                      if (template) updateField('target_node', template.node);
                    }}
                  >
                    {filteredTemplates.length === 0 ? (
                      <option value="">
                        {provisioningKind === 'lxc'
                          ? 'No LXC templates found in Proxmox storage'
                          : 'No VM templates found'}
                      </option>
                    ) : null}
                    {filteredTemplates.map((template) => (
                      <option
                        key={`${template.node}-${template.template_id}`}
                        value={template.template_id}
                      >
                        {template.name} ({template.type === 'lxc' ? 'LXC' : 'VM'} {template.template_id})
                      </option>
                    ))}
                  </select>
                  {provisioningKind === 'lxc' && selectedTemplate?.template_ref ? (
                    <span className="mt-1 block break-all font-mono text-xs text-zinc-500">
                      {selectedTemplate.template_ref}
                    </span>
                  ) : null}
                </label>
                <TextInput
                  label="Target node"
                  name="target_node"
                  value={formState.target_node}
                  onChange={updateField}
                />
                <TextInput
                  label="Network bridge"
                  name="network_bridge"
                  value={formState.network_bridge}
                  onChange={updateField}
                />
                <TextInput
                  label="CPU cores"
                  name="cpu_cores"
                  type="number"
                  value={formState.cpu_cores}
                  onChange={updateField}
                />
                <TextInput
                  label="RAM MB"
                  name="memory_mb"
                  type="number"
                  value={formState.memory_mb}
                  onChange={updateField}
                />
                <TextInput
                  label="Root disk GB"
                  name="disk_gb"
                  type="number"
                  value={formState.disk_gb}
                  onChange={updateField}
                />
                <TextInput
                  label="Static IP/CIDR"
                  name="static_ip_cidr"
                  value={formState.static_ip_cidr}
                  onChange={updateField}
                />
                <TextInput
                  label="Gateway"
                  name="gateway"
                  value={formState.gateway}
                  onChange={updateField}
                />
                <TextInput
                  label="DNS servers"
                  name="dns_servers_text"
                  value={formState.dns_servers_text}
                  onChange={updateField}
                />
                <TextInput
                  label={provisioningKind === 'lxc' ? 'Container SSH user' : 'Cloud-init user'}
                  name="cloud_init_username"
                  value={formState.cloud_init_username}
                  onChange={updateField}
                />
                <TextInput
                  label={provisioningKind === 'lxc' ? 'Container password' : 'Cloud-init password'}
                  name="cloud_init_password"
                  type="password"
                  value={formState.cloud_init_password}
                  onChange={updateField}
                />
                <TextInput
                  label="Environment"
                  name="environment"
                  value={formState.environment}
                  onChange={updateField}
                />
                <TextInput
                  label="Tags"
                  name="tags_text"
                  value={formState.tags_text}
                  onChange={updateField}
                />
                <TextInput
                  label="Description"
                  name="description"
                  value={formState.description}
                  onChange={updateField}
                />
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

              <details className="mt-5 rounded-md border border-zinc-200">
                <summary className="cursor-pointer list-none px-4 py-3 marker:hidden">
                  <h4 className="text-sm font-semibold text-zinc-950">Advanced storage</h4>
                  <p className="mt-1 text-xs text-zinc-500">
                    Optional disks and mount volumes for nodes that need extra storage.
                  </p>
                </summary>
                <div className="border-t border-zinc-200 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-950">
                      {provisioningKind === 'lxc' ? 'Additional mount volumes' : 'Additional disks'}
                    </h4>
                    <p className="mt-1 text-xs text-zinc-500">
                      {provisioningKind === 'lxc'
                        ? 'Root filesystem storage is inferred from the selected template storage for now.'
                        : 'Extra disks are added after the root disk as scsi1, scsi2, and onward by default.'}
                    </p>
                  </div>
                  <button
                    className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                    type="button"
                    onClick={() =>
                      updateField('additional_disks', [
                        ...formState.additional_disks,
                        {
                          size_gb: '32',
                          storage: diskStorageOptions[0]?.storage ?? 'local-lvm',
                          bus: 'scsi',
                        },
                      ])
                    }
                  >
                    Add disk
                  </button>
                </div>
                {formState.additional_disks.length ? (
                  <div className="mt-4 space-y-3">
                    {formState.additional_disks.map((disk, index) => (
                      <div key={index} className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
                        <label className="text-sm font-medium text-zinc-700">
                          Size GB
                          <input
                            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950"
                            min="1"
                            type="number"
                            value={disk.size_gb}
                            onChange={(event) =>
                              updateAdditionalDisk(index, { size_gb: event.target.value })
                            }
                          />
                        </label>
                        <label className="text-sm font-medium text-zinc-700">
                          Storage
                          <select
                            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950"
                            value={disk.storage}
                            onChange={(event) =>
                              updateAdditionalDisk(index, { storage: event.target.value })
                            }
                          >
                            {diskStorageOptions.length === 0 ? (
                              <option value={disk.storage}>{disk.storage || 'local-lvm'}</option>
                            ) : null}
                            {diskStorageOptions.map((storage) => (
                              <option
                                key={`${storage.node ?? 'cluster'}-${storage.storage}`}
                                value={storage.storage}
                              >
                                {storage.storage}
                                {storage.type ? ` (${storage.type})` : ''}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="text-sm font-medium text-zinc-700">
                          Bus
                          <select
                            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950"
                            value={disk.bus}
                            onChange={(event) =>
                              updateAdditionalDisk(index, {
                                bus: event.target.value as 'scsi' | 'virtio' | 'sata',
                              })
                            }
                          >
                            <option value="scsi">SCSI</option>
                            <option value="virtio">VirtIO</option>
                            <option value="sata">SATA</option>
                          </select>
                        </label>
                        <button
                          className="self-end rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50"
                          type="button"
                          onClick={() =>
                            updateField(
                              'additional_disks',
                              formState.additional_disks.filter(
                                (_, diskIndex) => diskIndex !== index,
                              ),
                            )
                          }
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                ) : null}
                </div>
              </details>

              <details className="mt-5 rounded-md border border-zinc-200">
                <summary className="cursor-pointer list-none px-4 py-3 marker:hidden">
                  <h4 className="text-sm font-semibold text-zinc-950">Bootstrap and profiles</h4>
                  <p className="mt-1 text-xs text-zinc-500">
                    Optional Jobs-backed profiles and packages to run after inventory registration.
                  </p>
                </summary>
                <div className="grid gap-4 border-t border-zinc-200 p-4 md:grid-cols-2">
                <MultiSelect
                  label="Bootstrap profiles"
                  options={profiles.map((profile) => ({
                    label: profile.name,
                    value: profile.id,
                  }))}
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
              </details>

              <div className="mt-5 flex justify-end">
                <button
                  className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:bg-zinc-300"
                  disabled={isSubmitting}
                  type="button"
                  onClick={handleSubmit}
                >
                  {isSubmitting ? 'Provisioning' : provisioningKind === 'lxc' ? 'Provision LXC' : 'Provision VM'}
                </button>
              </div>
            </>
          ) : null}
        </>
      </CollapsibleSection>

      <ProvisioningBatchHistory batches={batches} />
      <ProvisioningHistory requests={requests} onDelete={handleDeleteRequest} />
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

function BatchTextInput({
  label,
  name,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  name: keyof BatchFormState;
  value: string;
  type?: string;
  onChange: (name: keyof BatchFormState, value: string) => void;
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

function WizardSteps({ steps, currentIndex }: { steps: string[]; currentIndex: number }) {
  return (
    <ol className="mt-4 grid gap-2 md:grid-cols-3 xl:grid-cols-6">
      {steps.map((step, index) => (
        <li
          key={step}
          className={`rounded-md border px-3 py-2 text-xs font-semibold ${
            index <= currentIndex
              ? 'border-zinc-900 bg-zinc-950 text-white'
              : 'border-zinc-200 bg-zinc-50 text-zinc-500'
          }`}
        >
          <span className="mr-1 font-mono">{index + 1}</span>
          {step}
        </li>
      ))}
    </ol>
  );
}

function Notice({ tone, message }: { tone: 'success' | 'danger' | 'warning'; message: string }) {
  const className =
    tone === 'success'
      ? 'border-emerald-400/30 bg-emerald-950/40 text-emerald-100'
      : tone === 'warning'
        ? 'border-amber-400/30 bg-amber-950/40 text-amber-100'
        : 'border-rose-400/30 bg-rose-950/50 text-rose-100';
  return <p className={`rounded-lg border p-4 text-sm ${className}`}>{message}</p>;
}

function ProvisioningHistory({
  requests,
  onDelete,
}: {
  requests: ProvisioningRequest[];
  onDelete: (request: ProvisioningRequest) => void;
}) {
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
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={request.status} />
                <button
                  className="rounded-md border border-rose-400/50 px-2.5 py-1 text-xs font-semibold text-rose-200 transition hover:bg-rose-950/40"
                  type="button"
                  onClick={() => onDelete(request)}
                >
                  Delete
                </button>
              </div>
            </div>
            {request.error_message ? (
              <p className="mt-3 text-sm text-rose-700">{request.error_message}</p>
            ) : null}
            <p className="mt-3 text-xs text-zinc-500">
              Tasks: {request.proxmox_task_ids.length} | Bootstrap jobs:{' '}
              {request.bootstrap_job_ids.length}
            </p>
            <ProvisioningTimeline request={request} />
          </article>
        ))}
        {requests.length === 0 ? (
          <p className="text-sm text-zinc-500">No provisioning requests yet.</p>
        ) : null}
      </div>
    </section>
  );
}

function StatusPill({
  status,
}: {
  status: ProvisioningRequest['status'] | ProvisioningBatch['status'];
}) {
  const className =
    status === 'completed'
      ? 'bg-emerald-400/10 text-emerald-200 ring-emerald-400/40'
      : status === 'failed'
        ? 'bg-rose-400/10 text-rose-200 ring-rose-400/50'
        : status === 'partial_failed'
          ? 'bg-amber-400/10 text-amber-200 ring-amber-400/50'
          : 'bg-sky-400/10 text-sky-200 ring-sky-400/40';
  return (
    <span
      className={`inline-flex w-fit rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${className}`}
    >
      {status}
    </span>
  );
}

function ProvisioningBatchHistory({ batches }: { batches: ProvisioningBatch[] }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-200 px-5 py-4">
        <h3 className="text-base font-semibold text-zinc-950">Batch history</h3>
        <p className="mt-1 text-sm text-zinc-500">{batches.length} batch requests tracked.</p>
      </div>
      <div className="grid gap-3 p-4">
        {batches.map((batch) => (
          <article key={batch.id} className="rounded-lg border border-zinc-200 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h4 className="font-semibold text-zinc-950">{batch.name}</h4>
                <p className="mt-1 text-sm text-zinc-500">
                  {batch.count} VMs from VMID {batch.starting_vm_id}, starting at{' '}
                  {batch.starting_ip_cidr}
                </p>
              </div>
              <StatusPill status={batch.status} />
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <MetricCard label="Completed" value={`${batch.completed_count}`} />
              <MetricCard label="Failed" value={`${batch.failed_count}`} />
              <MetricCard label="Children" value={`${batch.requests.length}`} />
            </div>
            {batch.error_message ? (
              <p className="mt-3 whitespace-pre-line text-sm text-rose-700">
                {batch.error_message}
              </p>
            ) : null}
          </article>
        ))}
        {batches.length === 0 ? (
          <p className="text-sm text-zinc-500">No batch requests yet.</p>
        ) : null}
      </div>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
      <div className="text-xs font-medium uppercase tracking-normal text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function ProvisioningTimeline({ request }: { request: ProvisioningRequest }) {
  const items = provisioningTimelineItems(request);
  return (
    <ol className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <li key={item.label} className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-zinc-700">{item.label}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                item.state === 'done'
                  ? 'bg-emerald-100 text-emerald-700'
                  : item.state === 'failed'
                    ? 'bg-rose-100 text-rose-700'
                    : item.state === 'active'
                      ? 'bg-sky-100 text-sky-700'
                      : 'bg-zinc-100 text-zinc-500'
              }`}
            >
              {item.state}
            </span>
          </div>
          {item.detail ? (
            <p className="mt-1 break-all font-mono text-[11px] text-zinc-500">{item.detail}</p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function toPayload(
  formState: FormState,
  selectedTemplate: ProxmoxTemplate | null,
): CreateProvisioningPayload | null {
  if (
    !formState.vm_name ||
    !formState.cloud_init_hostname ||
    !formState.new_vm_id ||
    !formState.template_id ||
    !formState.static_ip_cidr ||
    !formState.gateway
  ) {
    return null;
  }

  return {
    vm_name: formState.vm_name.trim(),
    provisioning_type: selectedTemplate?.type === 'lxc' ? 'lxc' : 'qemu',
    target_node: formState.target_node || selectedTemplate?.node || '',
    template_id: Number(formState.template_id),
    template_ref: selectedTemplate?.template_ref ?? null,
    new_vm_id: Number(formState.new_vm_id),
    cpu_cores: Number(formState.cpu_cores),
    memory_mb: Number(formState.memory_mb),
    disk_gb: Number(formState.disk_gb),
    additional_disks: formState.additional_disks
      .filter((disk) => Number(disk.size_gb) > 0 && disk.storage.trim())
      .map((disk) => ({
        size_gb: Number(disk.size_gb),
        storage: disk.storage.trim(),
        bus: disk.bus,
      })),
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

function toBlueprintPayload(formState: FormState, name: string) {
  if (!name || !formState.template_id || !formState.target_node || !formState.gateway) {
    return null;
  }

  return {
    name,
    description: formState.description.trim() || null,
    target_node: formState.target_node.trim(),
    template_id: Number(formState.template_id),
    cpu_cores: Number(formState.cpu_cores),
    memory_mb: Number(formState.memory_mb),
    disk_gb: Number(formState.disk_gb),
    additional_disks: formState.additional_disks
      .filter((disk) => Number(disk.size_gb) > 0 && disk.storage.trim())
      .map((disk) => ({
        size_gb: Number(disk.size_gb),
        storage: disk.storage.trim(),
        bus: disk.bus,
      })),
    network_bridge: formState.network_bridge.trim(),
    environment: formState.environment.trim(),
    tags: splitCsv(formState.tags_text),
    start_on_boot: formState.start_on_boot,
    cloud_init_username: formState.cloud_init_username.trim(),
    ssh_public_key: formState.ssh_public_key.trim() || null,
    gateway: formState.gateway.trim(),
    dns_servers: splitCsv(formState.dns_servers_text),
    bootstrap_profile_ids: formState.bootstrap_profile_ids,
    bootstrap_package_ids: formState.bootstrap_package_ids,
  };
}

function toBatchPayload(formState: BatchFormState) {
  if (
    !formState.name.trim() ||
    !formState.blueprint_id ||
    !formState.count ||
    !formState.vm_name_pattern.trim() ||
    !formState.starting_vm_id ||
    !formState.starting_ip_cidr.trim()
  ) {
    return null;
  }

  return {
    name: formState.name.trim(),
    blueprint_id: formState.blueprint_id,
    count: Number(formState.count),
    vm_name_pattern: formState.vm_name_pattern.trim(),
    hostname_pattern: formState.hostname_pattern.trim() || null,
    starting_vm_id: Number(formState.starting_vm_id),
    starting_ip_cidr: formState.starting_ip_cidr.trim(),
    cloud_init_password: formState.cloud_init_password.trim() || null,
    description: formState.description.trim() || null,
  };
}

function reviewCompleteness(formState: FormState, selectedBlueprintId: string): number {
  if (!selectedBlueprintId) return 0;
  if (
    !formState.vm_name ||
    !formState.new_vm_id ||
    !formState.cloud_init_hostname ||
    !formState.static_ip_cidr
  )
    return 1;
  if (
    !formState.cloud_init_username ||
    (!formState.cloud_init_password && !formState.ssh_public_key)
  )
    return 2;
  if (formState.bootstrap_profile_ids.length || formState.bootstrap_package_ids.length) return 3;
  if (toPayload(formState, null)) return 4;
  return 3;
}

function provisioningTimelineItems(request: ProvisioningRequest): Array<{
  label: string;
  state: 'pending' | 'active' | 'done' | 'failed';
  detail?: string;
}> {
  const order = [
    ['validating_ip', 'Preflight'],
    ['cloning', 'Clone'],
    ['configuring', 'Cloud-init and disks'],
    ['starting', 'Start VM'],
    ['waiting_for_ssh', 'SSH readiness'],
    ['inventory_registration', 'Inventory'],
    ['bootstrap_running', 'Bootstrap'],
    ['completed', 'Complete'],
  ] as const;
  const currentIndex = order.findIndex(([status]) => status === request.status);
  return order.map(([status, label], index) => {
    let state: 'pending' | 'active' | 'done' | 'failed' = 'pending';
    if (request.status === 'failed') {
      state = index <= Math.max(currentIndex, 0) ? 'failed' : 'pending';
    } else if (currentIndex >= 0 && index < currentIndex) {
      state = 'done';
    } else if (currentIndex >= 0 && index === currentIndex) {
      state = status === 'completed' ? 'done' : 'active';
    }
    const detail =
      status === 'cloning'
        ? request.proxmox_task_ids[0]
        : status === 'configuring'
          ? request.proxmox_task_ids.slice(1, -1).join(', ')
          : status === 'bootstrap_running'
            ? request.bootstrap_job_ids.join(', ')
            : undefined;
    return { label, state, detail };
  });
}

function splitCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function ensureCsvValue(value: string, nextValue: string): string {
  const items = splitCsv(value);
  return items.includes(nextValue) ? value : [...items, nextValue].join(', ');
}
