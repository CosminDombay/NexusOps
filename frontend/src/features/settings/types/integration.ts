export type IntegrationType = 'infrastructure_provider' | 'monitoring' | 'networking' | 'database';
export type IntegrationProviderType = 'proxmox' | 'prometheus' | 'grafana' | 'loki' | 'tailscale' | 'custom';

export type Integration = {
  id: string;
  name: string;
  type: IntegrationType;
  provider_type: IntegrationProviderType;
  enabled: boolean;
  config: Record<string, unknown>;
  credential_refs: Record<string, string>;
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
