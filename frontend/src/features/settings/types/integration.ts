export type IntegrationType = 'infrastructure_provider' | 'monitoring' | 'networking' | 'database';
export type IntegrationProviderType = 'proxmox' | 'prometheus' | 'grafana' | 'loki' | 'tailscale' | 'custom';
export type IntegrationState = 'connected' | 'disconnected' | 'error' | 'disabled' | 'syncing';

export type Integration = {
  id: string;
  name: string;
  type: IntegrationType;
  provider_type: IntegrationProviderType;
  enabled: boolean;
  state: IntegrationState;
  config: Record<string, unknown>;
  credential_refs: Record<string, string>;
  last_successful_sync: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type IntegrationPayload = {
  name: string;
  type: IntegrationType;
  provider_type: IntegrationProviderType;
  enabled: boolean;
  config: Record<string, unknown>;
  credential_refs?: Record<string, string>;
};

export type IntegrationTestResult = {
  integration_id: string;
  status: string;
  message: string;
};
