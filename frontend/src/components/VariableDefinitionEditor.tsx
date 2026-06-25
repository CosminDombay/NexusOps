import { Plus, Trash2 } from 'lucide-react';

import type { Credential } from '../features/credentials/types/credential';

export type VariableDefinition = {
  name: string;
  description: string;
  default_value: string | null;
  required: boolean;
  sensitive: boolean;
  credential_type?: string | null;
  credential_ref?: string | null;
};

type VariableDefinitionEditorProps = {
  credentials?: Credential[];
  variables: VariableDefinition[];
  onChange: (variables: VariableDefinition[]) => void;
};

type VariableMode = 'text' | 'sensitive' | 'credential';

const variableModeOptions: Array<{ value: VariableMode; label: string }> = [
  { value: 'text', label: 'Text default' },
  { value: 'sensitive', label: 'Sensitive runtime' },
  { value: 'credential', label: 'Credential Manager asset' },
];

export function VariableDefinitionEditor({ credentials = [], variables, onChange }: VariableDefinitionEditorProps) {
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
        credential_ref: null,
      },
    ]);
  }

  function updateVariable(index: number, patch: Partial<VariableDefinition>) {
    onChange(variables.map((variable, currentIndex) => (currentIndex === index ? { ...variable, ...patch } : variable)));
  }

  function removeVariable(index: number) {
    onChange(variables.filter((_, currentIndex) => currentIndex !== index));
  }

  function variableMode(variable: VariableDefinition): VariableMode {
    if (variable.credential_ref) {
      return 'credential';
    }
    return variable.sensitive ? 'sensitive' : 'text';
  }

  function updateVariableMode(index: number, mode: VariableMode) {
    const credential = credentials[0];
    if (mode === 'credential') {
      updateVariable(index, {
        default_value: null,
        sensitive: true,
        credential_ref: credential?.id ?? null,
        credential_type: credential?.credential_type ?? null,
      });
      return;
    }
    updateVariable(index, {
      default_value: mode === 'text' ? variables[index]?.default_value ?? null : null,
      sensitive: mode === 'sensitive',
      credential_ref: null,
      credential_type: null,
    });
  }

  function updateCredentialRef(index: number, credentialId: string) {
    const credential = credentials.find((item) => item.id === credentialId);
    updateVariable(index, {
      credential_ref: credentialId || null,
      credential_type: credential?.credential_type ?? null,
      sensitive: true,
      default_value: null,
    });
  }

  return (
    <div className="xl:col-span-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-zinc-950">Variables</p>
          <p className="mt-1 text-xs text-zinc-500">Variables can use text defaults, sensitive runtime input, or a saved Credential Manager asset.</p>
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
                  Input source
                  <select
                    className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
                    value={variableMode(variable)}
                    onChange={(event) => updateVariableMode(index, event.target.value as VariableMode)}
                  >
                    {variableModeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="self-end rounded-md border border-rose-300 p-2 text-rose-700 hover:bg-rose-50" type="button" onClick={() => removeVariable(index)}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>

              {variableMode(variable) === 'text' ? (
                <label className="mt-3 block text-xs font-medium text-zinc-700">
                  Default value
                  <input
                    className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
                    value={variable.default_value ?? ''}
                    onChange={(event) => updateVariable(index, { default_value: event.target.value || null })}
                  />
                </label>
              ) : null}

              {variableMode(variable) === 'credential' ? (
                <label className="mt-3 block text-xs font-medium text-zinc-700">
                  Credential
                  <select
                    className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
                    value={variable.credential_ref ?? ''}
                    onChange={(event) => updateCredentialRef(index, event.target.value)}
                  >
                    <option value="">Select credential</option>
                    {credentials.map((credential) => (
                      <option key={credential.id} value={credential.id}>
                        {credential.name} ({credential.credential_type.replace('_', ' ')})
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <div className="mt-3 flex flex-wrap gap-4 text-sm text-zinc-700">
                <label className="inline-flex items-center gap-2">
                  <input checked={variable.required} type="checkbox" onChange={(event) => updateVariable(index, { required: event.target.checked })} />
                  Required
                </label>
                {variable.sensitive ? <span>Sensitive</span> : null}
                {variable.credential_ref ? <span>Credential Manager</span> : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
