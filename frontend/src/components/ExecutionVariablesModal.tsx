import { KeyRound, Loader2, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import type { Credential } from '../features/credentials/types/credential';

export type ExecutionVariable = {
  name: string;
  description: string;
  default_value: string | null;
  required: boolean;
  sensitive: boolean;
  credential_type?: string | null;
  credential_ref?: string | null;
};

export type ExecutionVariableValues = {
  variables: Record<string, string>;
  credential_refs: Record<string, string>;
  execution_credential_ref: string | null;
};

type VariableInputMode = 'value' | 'credential';

type ExecutionVariablesModalProps = {
  credentials: Credential[];
  isLoading?: boolean;
  isOpen: boolean;
  previewItems: string[];
  showExecutionCredential?: boolean;
  targetLabel: string;
  title: string;
  variables: ExecutionVariable[];
  onCancel: () => void;
  onConfirm: (values: ExecutionVariableValues) => void | Promise<void>;
};

export function ExecutionVariablesModal({
  credentials,
  isLoading = false,
  isOpen,
  previewItems,
  showExecutionCredential = false,
  targetLabel,
  title,
  variables,
  onCancel,
  onConfirm,
}: ExecutionVariablesModalProps) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [credentialRefs, setCredentialRefs] = useState<Record<string, string>>({});
  const [inputModes, setInputModes] = useState<Record<string, VariableInputMode>>({});
  const [executionCredentialRef, setExecutionCredentialRef] = useState('');
  const [error, setError] = useState<string | null>(null);

  const runtimeVariables = useMemo(() => variables, [variables]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setError(null);
    setValues(
      Object.fromEntries(
        runtimeVariables.map((variable) => [variable.name, variable.sensitive ? '' : variable.default_value ?? '']),
      ),
    );
    setCredentialRefs(
      Object.fromEntries(
        runtimeVariables.map((variable) => [variable.name, variable.credential_ref ?? '']),
      ),
    );
    setInputModes(
      Object.fromEntries(
        runtimeVariables.map((variable) => [
          variable.name,
          (variable.credential_ref || (variable.sensitive && variable.credential_type)) ? 'credential' : 'value',
        ]),
      ),
    );
    setExecutionCredentialRef('');
  }, [isOpen, runtimeVariables]);

  if (!isOpen) {
    return null;
  }

  async function handleConfirm() {
    const missingVariable = runtimeVariables.find((variable) => {
      const mode = inputModes[variable.name] ?? (variable.sensitive ? 'credential' : 'value');
      if (mode === 'credential') {
        return variable.required && !credentialRefs[variable.name]?.trim();
      }
      return variable.required && !values[variable.name]?.trim();
    });
    if (missingVariable) {
      setError(
        inputModes[missingVariable.name] === 'credential' || missingVariable.sensitive
          ? `${missingVariable.name} requires a credential.`
          : `${missingVariable.name} is required.`,
      );
      return;
    }

    await onConfirm({
      variables: Object.fromEntries(
        Object.entries(values).filter(([name, value]) => (inputModes[name] ?? 'value') === 'value' && value.trim() !== ''),
      ),
      credential_refs: Object.fromEntries(
        Object.entries(credentialRefs).filter(([name, value]) => (inputModes[name] ?? 'value') === 'credential' && value.trim() !== ''),
      ),
      execution_credential_ref: executionCredentialRef || null,
    });
  }

  function credentialsForVariable(variable: ExecutionVariable): Credential[] {
    if (!variable.credential_type) {
      return credentials;
    }
    return credentials.filter((credential) => credential.credential_type === variable.credential_type);
  }

  function setVariableMode(variable: ExecutionVariable, mode: VariableInputMode) {
    setInputModes((current) => ({ ...current, [variable.name]: mode }));
    setError(null);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-950">{title}</h2>
            <p className="mt-1 text-sm text-zinc-500">{targetLabel}</p>
          </div>
          <button className="rounded-md p-1 text-zinc-500 hover:bg-zinc-100" disabled={isLoading} type="button" onClick={onCancel}>
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="overflow-auto px-6 py-5">
          {error ? <p className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}

          <section>
            <h3 className="text-sm font-semibold text-zinc-950">Execution preview</h3>
            <ul className="mt-2 space-y-1 rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">
              {previewItems.length ? previewItems.map((item) => <li key={item}>{item}</li>) : <li>No steps selected.</li>}
            </ul>
          </section>

          {showExecutionCredential ? (
            <section className="mt-5">
              <label className="block text-sm font-medium text-zinc-700">
                <span className="inline-flex items-center gap-2">
                  <KeyRound className="h-4 w-4 text-zinc-500" aria-hidden="true" />
                  Execution / sudo credential
                </span>
                <select
                  className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950"
                  value={executionCredentialRef}
                  onChange={(event) => setExecutionCredentialRef(event.target.value)}
                >
                  <option value="">Use target saved credential or passwordless access</option>
                  {credentials
                    .filter((credential) => credential.credential_type === 'password' || credential.credential_type === 'ssh_password')
                    .map((credential) => (
                      <option key={credential.id} value={credential.id}>
                        {credential.name} ({credential.credential_type.replace('_', ' ')})
                      </option>
                    ))}
                </select>
                <span className="mt-1 block text-xs font-normal text-zinc-500">
                  Used by Jobs for commands that need sudo. Runtime variables below are only template inputs.
                </span>
              </label>
            </section>
          ) : null}

          {runtimeVariables.length ? (
            <section className="mt-5 space-y-4">
              <h3 className="text-sm font-semibold text-zinc-950">Runtime inputs</h3>
              {runtimeVariables.map((variable) => (
                <div key={variable.name} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-zinc-700">
                        {variable.name}{variable.required ? ' *' : ''}
                      </p>
                      {variable.description ? <p className="mt-1 text-xs text-zinc-500">{variable.description}</p> : null}
                    </div>
                    <div className="inline-flex h-9 overflow-hidden rounded-md border border-zinc-300 bg-white text-xs font-semibold">
                      <button
                        className={`px-3 ${inputModes[variable.name] !== 'credential' ? 'bg-zinc-950 text-white' : 'text-zinc-600 hover:bg-zinc-50'}`}
                        type="button"
                        onClick={() => setVariableMode(variable, 'value')}
                      >
                        {variable.sensitive ? 'Sensitive value' : 'Value'}
                      </button>
                      <button
                        className={`inline-flex items-center gap-1 border-l border-zinc-300 px-3 ${inputModes[variable.name] === 'credential' ? 'bg-zinc-950 text-white' : 'text-zinc-600 hover:bg-zinc-50'}`}
                        type="button"
                        onClick={() => setVariableMode(variable, 'credential')}
                      >
                        <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                        Credential
                      </button>
                    </div>
                  </div>

                  {(inputModes[variable.name] ?? (variable.sensitive ? 'credential' : 'value')) === 'credential' ? (
                    <select
                      className="mt-3 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950"
                      value={credentialRefs[variable.name] ?? ''}
                      onChange={(event) => setCredentialRefs((current) => ({ ...current, [variable.name]: event.target.value }))}
                    >
                      <option value="">Select credential</option>
                      {credentialsForVariable(variable).map((credential) => (
                        <option key={credential.id} value={credential.id}>
                          {credential.name} ({credential.credential_type.replace('_', ' ')})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="mt-3 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-950"
                      type={variable.sensitive ? 'password' : 'text'}
                      value={values[variable.name] ?? ''}
                      onChange={(event) => setValues((current) => ({ ...current, [variable.name]: event.target.value }))}
                    />
                  )}
                </div>
              ))}
            </section>
          ) : (
            <p className="mt-5 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500">
              No runtime variables are required.
            </p>
          )}
        </div>

        <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-3">
          <div className="flex justify-end gap-3">
            <button className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold text-zinc-700" disabled={isLoading} type="button" onClick={onCancel}>
              Cancel
            </button>
            <button className="inline-flex items-center gap-2 rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-zinc-300" disabled={isLoading} type="button" onClick={handleConfirm}>
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
              Run
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
