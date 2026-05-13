export type PackageDefinition = {
  id: string;
  name: string;
  category: string;
  supported_os: string[];
  install_command: string;
  validation_command: string;
  tags: string[];
  description: string;
  is_builtin: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type CreatePackageDefinitionPayload = {
  id: string;
  name: string;
  category: string;
  supported_os: string[];
  install_command: string;
  validation_command: string;
  tags: string[];
  description: string;
};
