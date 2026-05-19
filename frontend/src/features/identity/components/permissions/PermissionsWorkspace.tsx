import type { PermissionPreset, PermissionTemplate } from '../../types/identity';
import { PermissionChip, SectionCard } from '../common/IdentityPrimitives';

export function PermissionsWorkspace({
  permissions,
  presets,
}: {
  permissions: PermissionTemplate[];
  presets: PermissionPreset[];
}) {
  return (
    <div className="space-y-4">
      <section className="rounded-md border border-slate-700 bg-slate-900/80 p-5">
        <h2 className="text-xl font-semibold text-white">Filesystem Permissions</h2>
        <p className="mt-1 text-sm text-slate-400">Reusable permission templates and presets for Linux path ownership and mode replication.</p>
      </section>
      <SectionCard title="Permission Presets">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {presets.map((preset) => (
            <div key={preset.id} className="rounded-md border border-slate-700 bg-slate-950/50 p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold text-white">{preset.name}</p>
                <PermissionChip label={preset.mode} tone="observe" />
              </div>
              <p className="mt-2 text-sm text-slate-400">{preset.description}</p>
            </div>
          ))}
        </div>
      </SectionCard>
      <SectionCard title="Saved Templates">
        <div className="space-y-2">
          {permissions.map((permission) => (
            <div key={permission.id} className="grid gap-3 rounded-md border border-slate-700 bg-slate-950/50 p-3 md:grid-cols-[1fr_auto]">
              <div>
                <p className="font-mono text-sm font-semibold text-white">{permission.path}</p>
                <p className="mt-1 text-xs text-slate-400">{permission.description ?? 'No description'}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {permission.owner ? <PermissionChip label={`owner ${permission.owner}`} /> : null}
                {permission.group ? <PermissionChip label={`group ${permission.group}`} /> : null}
                {permission.mode ? <PermissionChip label={permission.mode} tone="observe" /> : null}
              </div>
            </div>
          ))}
          {!permissions.length ? <p className="text-sm text-slate-400">No saved permission templates yet.</p> : null}
        </div>
      </SectionCard>
    </div>
  );
}

