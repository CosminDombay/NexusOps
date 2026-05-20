export type MonitoringProviderStatus = {
  provider_type: string;
  configured: boolean;
  reachable: boolean;
  integration_id: string | null;
  url: string | null;
  error: string | null;
  role: string;
};

export type ServerMetrics = {
  server_id: string;
  hostname: string;
  ip_address: string;
  monitoring_targets: string[];
  online: boolean;
  cpu_usage_percent: number | null;
  memory_usage_percent: number | null;
  disk_usage_percent: number | null;
  uptime_seconds: number | null;
  grafana_url: string | null;
  prometheus_url: string | null;
  loki_url: string | null;
  advanced_metrics_url: string | null;
  advanced_logs_url: string | null;
  metrics_error: string | null;
  logs_error: string | null;
  monitoring_state: string;
  metrics_available: boolean;
  logs_available: boolean;
  node_exporter_detected: boolean;
  cadvisor_detected: boolean;
  promtail_detected: boolean;
  scrape_target_health: string;
  stale_metrics: boolean;
  readiness_reasons: string[];
  collected_at: string;
};

export type MonitoringOverview = {
  total_servers: number;
  online_servers: number;
  offline_servers: number;
  observable_servers: number;
  degraded_servers: number;
  metrics_missing_servers: number;
  logs_missing_servers: number;
  stale_metrics_servers: number;
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
