import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Download, FileArchive, RefreshCw, Upload } from 'lucide-react';

import { PageHeader } from '../../../components/layout/PageHeader';
import { PageActionButton } from '../../../components/operations/OperationalComponents';
import { getApiErrorMessage } from '../../../lib/api/client';
import { useAuth } from '../../auth/hooks/useAuth';
import { exportDeployment, importDeployment, listDeployments } from '../../deployments/api/deploymentsApi';
import type { Deployment } from '../../deployments/types/deployment';
import { exportIdentityBundle, importIdentityBundle } from '../../identity/api/identityApi';
import { exportPackageDefinition, importPackageDefinition, listPackageDefinitions } from '../../packages/api/packagesApi';
import type { PackageDefinition } from '../../packages/types/package';
import { exportProfile, importProfile, listProfiles } from '../../profiles/api/profilesApi';
import type { InfrastructureProfile } from '../../profiles/types/profile';

type ExchangeDomain = 'packages' | 'profiles' | 'deployments' | 'identity';
type DocumentFormat = 'json' | 'yaml';
type ImportStrategy = 'clone_on_conflict' | 'create';

type ImportPreview = {
  domain: ExchangeDomain;
  filename: string;
  format: DocumentFormat;
  content: string;
};

type ExchangeItem = {
  id: string;
  name: string;
  detail: string;
};

const domainLabels: Record<ExchangeDomain, string> = {
  packages: 'Packages',
  profiles: 'Profiles',
  deployments: 'Deployments',
  identity: 'Identity bundle',
};

const domainKinds: Record<ExchangeDomain, string> = {
  packages: 'nexusops.package',
  profiles: 'nexusops.profile',
  deployments: 'nexusops.deployment',
  identity: 'nexusops.identity_bundle',
};

export function DataExchangePage() {
  const { user } = useAuth();
  const canUseIdentity = user?.role === 'admin' || user?.is_superuser;
  const [packages, setPackages] = useState<PackageDefinition[]>([]);
  const [profiles, setProfiles] = useState<InfrastructureProfile[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [selectedIds, setSelectedIds] = useState<Record<Exclude<ExchangeDomain, 'identity'>, string>>({
    packages: '',
    profiles: '',
    deployments: '',
  });
  const [exportFormat, setExportFormat] = useState<DocumentFormat>('yaml');
  const [importStrategy, setImportStrategy] = useState<ImportStrategy>('clone_on_conflict');
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const fileInputs = {
    packages: useRef<HTMLInputElement | null>(null),
    profiles: useRef<HTMLInputElement | null>(null),
    deployments: useRef<HTMLInputElement | null>(null),
    identity: useRef<HTMLInputElement | null>(null),
  };

  const packageItems = useMemo(
    () =>
      packages.map((item) => ({
        id: item.id,
        name: item.name,
        detail: [item.category, item.is_builtin ? 'built-in' : 'custom'].filter(Boolean).join(' / '),
      })),
    [packages],
  );
  const profileItems = useMemo(
    () =>
      profiles.map((item) => ({
        id: item.id,
        name: item.name,
        detail: [item.category, `${item.steps.length} steps`].filter(Boolean).join(' / '),
      })),
    [profiles],
  );
  const deploymentItems = useMemo(
    () =>
      deployments.map((item) => ({
        id: item.id,
        name: item.name,
        detail: item.targets.length
          ? `${item.targets.length} target${item.targets.length === 1 ? '' : 's'}`
          : 'planning draft',
      })),
    [deployments],
  );

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextPackages, nextProfiles, nextDeployments] = await Promise.all([
        listPackageDefinitions(),
        listProfiles(),
        listDeployments(),
      ]);
      setPackages(nextPackages);
      setProfiles(nextProfiles);
      setDeployments(nextDeployments);
      setSelectedIds({
        packages: nextPackages[0]?.id ?? '',
        profiles: nextProfiles[0]?.id ?? '',
        deployments: nextDeployments[0]?.id ?? '',
      });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleExport(domain: ExchangeDomain) {
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    setWarnings([]);
    try {
      const exported =
        domain === 'packages'
          ? await exportPackageDefinition(selectedIds.packages, exportFormat)
          : domain === 'profiles'
            ? await exportProfile(selectedIds.profiles, exportFormat)
            : domain === 'deployments'
              ? await exportDeployment(selectedIds.deployments, exportFormat)
              : await exportIdentityBundle(exportFormat);
      downloadTextFile(exported.filename, exported.content, mimeTypeFor(exported.format));
      setSuccess(`Exported ${domainLabels[domain]}.`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function handleImportFile(domain: ExchangeDomain, file: File | null) {
    if (!file) return;
    setError(null);
    setSuccess(null);
    setWarnings([]);
    try {
      const content = await file.text();
      setImportPreview({
        domain,
        filename: file.name,
        format: importFormatFromFile(file.name),
        content,
      });
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      const input = fileInputs[domain].current;
      if (input) input.value = '';
    }
  }

  async function confirmImport() {
    if (!importPreview) return;
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    setWarnings([]);
    try {
      const result =
        importPreview.domain === 'packages'
          ? await importPackageDefinition(importPreview.content, importPreview.format, importStrategy)
          : importPreview.domain === 'profiles'
            ? await importProfile(importPreview.content, importPreview.format, importStrategy)
            : importPreview.domain === 'deployments'
              ? await importDeployment(importPreview.content, importPreview.format, importStrategy)
              : await importIdentityBundle(importPreview.content, importPreview.format, importStrategy);
      setWarnings(result.warnings ?? []);
      setSuccess(importSuccessMessage(importPreview.domain, result));
      setImportPreview(null);
      await refresh();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  function updateSelectedId(domain: Exclude<ExchangeDomain, 'identity'>, id: string) {
    setSelectedIds((current) => ({ ...current, [domain]: id }));
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Data Exchange"
        description="Portable NexusOps documents for reusable operational definitions and local desired-state templates."
        actions={
          <>
            <PageActionButton icon={RefreshCw} tone="secondary" onClick={() => void refresh()}>
              Refresh
            </PageActionButton>
          </>
        }
      />

      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {success}
        </div>
      ) : null}
      {warnings.length ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {warnings.join(' ')}
        </div>
      ) : null}

      <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-4">
          <Metric label="Packages" value={packages.length} />
          <Metric label="Profiles" value={profiles.length} />
          <Metric label="Deployments" value={deployments.length} />
          <Metric label="Identity" value={canUseIdentity ? 'available' : 'admin only'} />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <ExchangePanel
          domain="packages"
          format={exportFormat}
          inputRef={fileInputs.packages}
          isLoading={isLoading}
          isWorking={isWorking}
          items={packageItems}
          selectedId={selectedIds.packages}
          strategy={importStrategy}
          onExport={() => void handleExport('packages')}
          onFile={(file) => void handleImportFile('packages', file)}
          onFormatChange={setExportFormat}
          onSelectedIdChange={(id) => updateSelectedId('packages', id)}
          onStrategyChange={setImportStrategy}
        />
        <ExchangePanel
          domain="profiles"
          format={exportFormat}
          inputRef={fileInputs.profiles}
          isLoading={isLoading}
          isWorking={isWorking}
          items={profileItems}
          selectedId={selectedIds.profiles}
          strategy={importStrategy}
          onExport={() => void handleExport('profiles')}
          onFile={(file) => void handleImportFile('profiles', file)}
          onFormatChange={setExportFormat}
          onSelectedIdChange={(id) => updateSelectedId('profiles', id)}
          onStrategyChange={setImportStrategy}
        />
        <ExchangePanel
          domain="deployments"
          format={exportFormat}
          inputRef={fileInputs.deployments}
          isLoading={isLoading}
          isWorking={isWorking}
          items={deploymentItems}
          selectedId={selectedIds.deployments}
          strategy={importStrategy}
          onExport={() => void handleExport('deployments')}
          onFile={(file) => void handleImportFile('deployments', file)}
          onFormatChange={setExportFormat}
          onSelectedIdChange={(id) => updateSelectedId('deployments', id)}
          onStrategyChange={setImportStrategy}
        />
        <IdentityExchangePanel
          disabled={!canUseIdentity || isWorking}
          format={exportFormat}
          inputRef={fileInputs.identity}
          strategy={importStrategy}
          onExport={() => void handleExport('identity')}
          onFile={(file) => void handleImportFile('identity', file)}
          onFormatChange={setExportFormat}
          onStrategyChange={setImportStrategy}
        />
      </section>

      {importPreview ? (
        <ImportPreviewModal
          isWorking={isWorking}
          preview={importPreview}
          strategy={importStrategy}
          onClose={() => setImportPreview(null)}
          onConfirm={() => void confirmImport()}
          onStrategyChange={setImportStrategy}
        />
      ) : null}
    </div>
  );
}

function ExchangePanel({
  domain,
  items,
  selectedId,
  format,
  strategy,
  inputRef,
  isLoading,
  isWorking,
  onSelectedIdChange,
  onFormatChange,
  onStrategyChange,
  onExport,
  onFile,
}: {
  domain: Exclude<ExchangeDomain, 'identity'>;
  items: ExchangeItem[];
  selectedId: string;
  format: DocumentFormat;
  strategy: ImportStrategy;
  inputRef: RefObject<HTMLInputElement | null>;
  isLoading: boolean;
  isWorking: boolean;
  onSelectedIdChange: (id: string) => void;
  onFormatChange: (format: DocumentFormat) => void;
  onStrategyChange: (strategy: ImportStrategy) => void;
  onExport: () => void;
  onFile: (file: File | null) => void;
}) {
  const selected = items.find((item) => item.id === selectedId);
  return (
    <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
      <PanelHeader domain={domain} count={items.length} />
      <div className="mt-4 grid gap-3">
        <label className="block">
          <span className="text-xs font-semibold uppercase text-zinc-500">Export target</span>
          <select
            className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950"
            disabled={isLoading || isWorking || !items.length}
            value={selectedId}
            onChange={(event) => onSelectedIdChange(event.target.value)}
          >
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <p className="min-h-5 text-sm text-zinc-500">{selected?.detail ?? 'No records available.'}</p>
        <SharedControls
          format={format}
          strategy={strategy}
          onFormatChange={onFormatChange}
          onStrategyChange={onStrategyChange}
        />
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-900 bg-zinc-900 px-3 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:border-zinc-300 disabled:bg-zinc-300"
            disabled={isWorking || !selectedId}
            type="button"
            onClick={onExport}
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Export
          </button>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
            disabled={isWorking}
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="h-4 w-4" aria-hidden="true" />
            Import
          </button>
          <input
            ref={inputRef as RefObject<HTMLInputElement>}
            accept=".json,.yaml,.yml,application/json,application/x-yaml,text/yaml"
            className="hidden"
            type="file"
            onChange={(event) => onFile(event.target.files?.[0] ?? null)}
          />
        </div>
      </div>
    </section>
  );
}

function IdentityExchangePanel({
  disabled,
  format,
  strategy,
  inputRef,
  onFormatChange,
  onStrategyChange,
  onExport,
  onFile,
}: {
  disabled: boolean;
  format: DocumentFormat;
  strategy: ImportStrategy;
  inputRef: RefObject<HTMLInputElement | null>;
  onFormatChange: (format: DocumentFormat) => void;
  onStrategyChange: (strategy: ImportStrategy) => void;
  onExport: () => void;
  onFile: (file: File | null) => void;
}) {
  return (
    <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
      <PanelHeader domain="identity" count={1} />
      <div className="mt-4 grid gap-3">
        <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
          Managed users, groups, SSH public keys, and filesystem permission templates.
        </div>
        <SharedControls
          format={format}
          strategy={strategy}
          onFormatChange={onFormatChange}
          onStrategyChange={onStrategyChange}
        />
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-900 bg-zinc-900 px-3 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:border-zinc-300 disabled:bg-zinc-300"
            disabled={disabled}
            type="button"
            onClick={onExport}
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Export
          </button>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
            disabled={disabled}
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="h-4 w-4" aria-hidden="true" />
            Import
          </button>
          <input
            ref={inputRef as RefObject<HTMLInputElement>}
            accept=".json,.yaml,.yml,application/json,application/x-yaml,text/yaml"
            className="hidden"
            type="file"
            onChange={(event) => onFile(event.target.files?.[0] ?? null)}
          />
        </div>
      </div>
    </section>
  );
}

function PanelHeader({ domain, count }: { domain: ExchangeDomain; count: number }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold text-zinc-950">{domainLabels[domain]}</h2>
        <p className="mt-1 font-mono text-xs text-zinc-500">{domainKinds[domain]}</p>
      </div>
      <span className="inline-flex rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-700 ring-1 ring-inset ring-zinc-200">
        {count}
      </span>
    </div>
  );
}

function SharedControls({
  format,
  strategy,
  onFormatChange,
  onStrategyChange,
}: {
  format: DocumentFormat;
  strategy: ImportStrategy;
  onFormatChange: (format: DocumentFormat) => void;
  onStrategyChange: (strategy: ImportStrategy) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="block">
        <span className="text-xs font-semibold uppercase text-zinc-500">Export format</span>
        <select
          className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950"
          value={format}
          onChange={(event) => onFormatChange(event.target.value as DocumentFormat)}
        >
          <option value="yaml">YAML</option>
          <option value="json">JSON</option>
        </select>
      </label>
      <label className="block">
        <span className="text-xs font-semibold uppercase text-zinc-500">Import policy</span>
        <select
          className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950"
          value={strategy}
          onChange={(event) => onStrategyChange(event.target.value as ImportStrategy)}
        >
          <option value="clone_on_conflict">Clone on conflict</option>
          <option value="create">Create only</option>
        </select>
      </label>
    </div>
  );
}

function ImportPreviewModal({
  preview,
  strategy,
  isWorking,
  onStrategyChange,
  onClose,
  onConfirm,
}: {
  preview: ImportPreview;
  strategy: ImportStrategy;
  isWorking: boolean;
  onStrategyChange: (strategy: ImportStrategy) => void;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-zinc-950/70 px-4 py-8">
      <section className="w-full max-w-3xl rounded-md border border-zinc-200 bg-white shadow-xl">
        <header className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-950">Import Preview</h2>
            <p className="mt-1 text-sm text-zinc-500">{preview.filename}</p>
          </div>
          <FileArchive className="h-5 w-5 text-zinc-500" aria-hidden="true" />
        </header>
        <div className="grid gap-4 p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Domain" value={domainLabels[preview.domain]} />
            <Metric label="Format" value={preview.format.toUpperCase()} />
            <Metric label="Kind" value={domainKinds[preview.domain]} />
          </div>
          <label className="block">
            <span className="text-xs font-semibold uppercase text-zinc-500">Import policy</span>
            <select
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950"
              value={strategy}
              onChange={(event) => onStrategyChange(event.target.value as ImportStrategy)}
            >
              <option value="clone_on_conflict">Clone on conflict</option>
              <option value="create">Create only</option>
            </select>
          </label>
          <pre className="max-h-72 overflow-auto rounded-md bg-zinc-950 p-3 font-mono text-xs leading-5 text-zinc-50">
            {preview.content.slice(0, 4000)}
            {preview.content.length > 4000 ? '\n...' : ''}
          </pre>
          <div className="flex justify-end gap-2">
            <button
              className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
              disabled={isWorking}
              type="button"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="rounded-md border border-zinc-900 bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800 disabled:border-zinc-300 disabled:bg-zinc-300"
              disabled={isWorking}
              type="button"
              onClick={onConfirm}
            >
              Import
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
      <p className="text-xs font-semibold uppercase text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-zinc-950">{value}</p>
    </div>
  );
}

function importFormatFromFile(filename: string): DocumentFormat {
  return filename.toLowerCase().endsWith('.json') ? 'json' : 'yaml';
}

function mimeTypeFor(format: DocumentFormat): string {
  return format === 'json' ? 'application/json' : 'application/x-yaml';
}

function downloadTextFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function importSuccessMessage(domain: ExchangeDomain, result: unknown): string {
  if (domain === 'packages') {
    const imported = result as { package: { name: string }; status: string };
    return `Imported package ${imported.package.name}${imported.status === 'cloned' ? ' as a clone' : ''}.`;
  }
  if (domain === 'profiles') {
    const imported = result as { profile: { name: string }; status: string };
    return `Imported profile ${imported.profile.name}${imported.status === 'cloned' ? ' as a clone' : ''}.`;
  }
  if (domain === 'deployments') {
    const imported = result as { deployment: { name: string }; status: string };
    return `Imported deployment ${imported.deployment.name}${imported.status === 'cloned' ? ' as a clone' : ''}.`;
  }
  const imported = result as {
    users: unknown[];
    groups: unknown[];
    ssh_keys: unknown[];
    permissions: unknown[];
    status: string;
  };
  const count =
    imported.users.length + imported.groups.length + imported.ssh_keys.length + imported.permissions.length;
  return `Imported ${count} identity object${count === 1 ? '' : 's'}${imported.status === 'cloned' ? ' with cloned names' : ''}.`;
}
