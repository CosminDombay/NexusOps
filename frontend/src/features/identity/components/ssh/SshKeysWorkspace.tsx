import { KeyRound } from 'lucide-react';

import type { SSHKey } from '../../types/identity';
import { SectionCard } from '../common/IdentityPrimitives';

export function SshKeysWorkspace({ keys }: { keys: SSHKey[] }) {
  return (
    <div className="space-y-4">
      <section className="rounded-md border border-slate-700 bg-slate-900/80 p-5">
        <h2 className="text-xl font-semibold text-white">SSH Keys</h2>
        <p className="mt-1 text-sm text-slate-400">Public keys available for deployment and revocation against managed Linux users.</p>
      </section>
      <SectionCard title="Managed SSH Key Records">
        <div className="grid gap-3 lg:grid-cols-2">
          {keys.map((keyRecord) => (
            <div key={keyRecord.id} className="rounded-md border border-slate-700 bg-slate-950/50 p-3">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-cyan-200" aria-hidden="true" />
                <p className="font-semibold text-white">{keyRecord.name}</p>
              </div>
              <p className="mt-2 line-clamp-2 font-mono text-xs text-slate-400">{keyRecord.public_key}</p>
            </div>
          ))}
          {!keys.length ? <p className="text-sm text-slate-400">No SSH keys yet.</p> : null}
        </div>
      </SectionCard>
    </div>
  );
}

