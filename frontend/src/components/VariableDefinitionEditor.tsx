import { Plus, Trash2 } from 'lucide-react';

import type { CredentialType } from '../features/credentials/types/credential';

export type VariableDefinition = {
  name: string;
  description: string;
  default_value: string | null;
  required: boolean;
  sensitive: boolean;
  credential_type?: string | null;
};

type VariableDefinitionEditorProps = {
  variables: VariableDefinition[];
  onChange: (variables: VariableDefinition[]) => void;
};

const credentialTypeOptions: Array<{ value: '' | CredentialType; label: string }> = [
  { value: '', label: 'Any credential type' },
  { value: 'env_secret', label: 'Environment secret' },
  { value: 'api_token', label: 'API token' },
  { value: 'password', label: 'Password' },
  { value: 'ssh_password', label: 'SSH password' },
  { value: 'ssh_key', label: 'SSH key' },
];

export function VariableDefinitionEditor({ variables, onChange }: VariableDefinitionEditorProps) {
  function addVariable() {
    onChange([
      ...variables,
      {
        name: '',
        description: '',
        default_value: null,
        required: false,
        sensitive: false,
        credential_type: null,
      },
    ]);
  }

  function updateVariable(index: number, patch: Partial<VariableDefinition>) {
    onChange(variables.map((variable, currentIndex) => (currentIndex === index ? { ...variable, ...patch } : variable)));
  }

  function removeVariable(index: number) {
    onChange(variables.filter((_, currentIndex) => currentIndex !== index));
  }

  return (
    <div className="xl:col-span-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-zinc-950">Variables</p>
          <p className="mt-1 text-xs text-zinc-500">Sensitive variables are satisfied with Credential Manager references at runtime.</p>
        </div>
        <button className="inline-flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50" type="button" onClick={addVariable}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add variable
        </button>
      </div>

      {variables.length === 0 ? (
        <p className="mt-3 rounded-md border border-dashed border-zinc-300 px-3 py-4 text-sm text-zinc-500">No runtime variables defined.</p>
      ) : (
        <div className="mt-3 space-y-3">
          {variables.map((variable, index) => (
            <div key={index} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_auto]">
                <label className="text-xs font-medium text-zinc-700">
                  Name
                  <input className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm" value={variable.name} onChange={(event) => updateVariable(index, { name: event.target.value })} />
                </label>
                <label className="text-xs font-medium text-zinc-700">
                  Description
                  <input className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm" value={variable.description} onChange={(event) => updateVariable(index, { description: event.target.value })} />
                </label>
                <label className="text-xs font-medium text-zinc-700">
                  {variable.sensitive ? 'Credential type' : 'Default value'}
                  {variable.sensitive ? (
                    <select
                      className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
                      value={variable.credential_type ?? ''}
                      onChange={(event) => updateVariable(index, { credential_type: event.target.value || null })}
                    >
                      {credentialTypeOptions.map((option) => (
                        <option key={option.value || 'any'} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
                      value={variable.default_value ?? ''}
                      onChange={(event) => updateVariable(index, { default_value: event.target.value || null })}
                    />
                  )}
                </label>
                <button className="self-end rounded-md border border-rose-300 p-2 text-rose-700 hover:bg-rose-50" type="button" onClick={() => removeVariable(index)}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              <div className="mt-3 flex flex-wrap gap-4 text-sm text-zinc-700">
                <label className="inline-flex items-center gap-2">
                  <input checked={variable.required} type="checkbox" onChange={(event) => updateVariable(index, { required: event.target.checked })} />
                  Required
                </label>
                <label className="inline-flex items-center gap-2">
                  <input
                    checked={variable.sensitive}
                    type="checkbox"
                    onChange={(event) =>
                      updateVariable(index, {
                        sensitive: event.target.checked,
                        default_value: event.target.checked ? null : variable.default_value,
                        credential_type: event.target.checked ? variable.credential_type ?? null : null,
                      })
                    }
                  />
                  Sensitive
                </label>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
