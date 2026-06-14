export type CredentialType = 'password' | 'ssh_password' | 'ssh_key' | 'api_token' | 'env_secret';

export type CredentialScope = 'global' | 'project' | 'environment';

export type Credential = {
  id: string;
  name: string;
  description: string;
  credential_type: CredentialType;
  username: string | null;
  masked_secret: string;
  tags: string[];
  scope: CredentialScope;
  deleted_at: string | null;
  deleted_by: string | null;
  delete_reason: string | null;
  reference_count: number;
  created_at: string;
  updated_at: string;
};

export type CreateCredentialPayload = {
  name: string;
  description: string;
  credential_type: CredentialType;
  username?: string | null;
  secret?: string | null;
  private_key?: string | null;
  passphrase?: string | null;
  tags: string[];
  scope: CredentialScope;
};

export type UpdateCredentialPayload = Partial<CreateCredentialPayload>;

export type CredentialReference = {
  reference_type: string;
  reference_id: string;
  name: string;
  field: string;
  detail: string | null;
};

export type CredentialUsage = {
  credential_id: string;
  references: CredentialReference[];
  reference_count: number;
};
