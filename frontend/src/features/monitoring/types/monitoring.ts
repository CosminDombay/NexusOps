export type MonitoringProviderStatus = {
  provider_type: string;
  configured: boolean;
  reachable: boolean;
  integration_id: string | null;
  url: string | null;
  error: string | null;
};

export type ServerMetrics = {
  server_id: string;
  hostname: string;
  ip_address: string;
  online: boolean;
  cpu_usage_percent: number | null;
  memory_usage_percent: number | null;
  disk_usage_percent: number | null;
  uptime_seconds: number | null;
  grafana_url: string | null;
  prometheus_url: string | null;
  loki_url: string | null;
  metrics_error: string | null;
  collected_at: string;
};

export type MonitoringOverview = {
  total_servers: number;
  online_servers: number;
  offline_servers: number;
  providers: MonitoringProviderStatus[];
  servers: ServerMetrics[];
};

export type PrometheusHealth = {
  configured: boolean;
  reachable: boolean;
  error: string | null;
  integration_id: string | null;
  prometheus_url: string | null;
  grafana_url: string | null;
  loki_url: string | null;
  providers: MonitoringProviderStatus[];
};
