export type PackageDefinition = {
  id: string;
  name: string;
  category: string;
  supported_os: string[];
  install_command: string;
  uninstall_command: string;
  validation_command: string;
  variables: TemplateVariable[];
  tags: string[];
  description: string;
  is_builtin: boolean;
  is_modified: boolean;
  base_version: string | null;
  source_template_id: string | null;
  modified_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type TemplateVariable = {
  name: string;
  description: string;
  default_value: string | null;
  required: boolean;
  sensitive: boolean;
  credential_type?: string | null;
  credential_ref?: string | null;
};

export type CreatePackageDefinitionPayload = {
  id: string;
  name: string;
  category: string;
  supported_os: string[];
  install_command: string;
  uninstall_command: string;
  validation_command: string;
  variables: TemplateVariable[];
  tags: string[];
  description: string;
};

export type UpdatePackageDefinitionPayload = Omit<CreatePackageDefinitionPayload, 'id'>;
