export type ServerEnvironment = 'development' | 'staging' | 'production' | 'testing' | 'lab';

export type ServerStatus = 'unknown' | 'online' | 'offline' | 'maintenance';

export type ServerSshAuthMethod = 'key' | 'password';

export type Server = {
  id: string;
  hostname: string;
  ip_address: string;
  operating_system: string;
  vmid: string | null;
  environment: ServerEnvironment;
  tags: string[];
  ssh_port: number;
  ssh_username: string;
  ssh_auth_method: ServerSshAuthMethod;
  ssh_private_key_path: string | null;
  status: ServerStatus;
  provider: string;
  created_at: string;
  updated_at: string;
};

export type CreateServerPayload = {
  hostname: string;
  ip_address: string;
  operating_system: string;
  environment: ServerEnvironment;
  provider: string;
  ssh_port: number;
  ssh_username: string;
  ssh_auth_method: ServerSshAuthMethod;
  ssh_password?: string | null;
  ssh_private_key_path?: string | null;
};
