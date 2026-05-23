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
  monitoring_interface: string | null;
  monitoring_strategy: string;
  online: boolean;
  cpu_usage_percent: number | null;
  memory_usage_percent: number | null;
  disk_usage_percent: number | null;
  uptime_seconds: number | null;
  grafana_url: string | null;
  prometheus_url: string | null;
  loki_url: string | null;
  advanced_metrics_url: string | null;
  container_metrics_url: string | null;
  advanced_logs_url: string | null;
  open_grafana_url: string | null;
  metrics_error: string | null;
  logs_error: string | null;
  monitoring_state: string;
  monitoring_status: string;
  node_exporter_status: string;
  promtail_status: string;
  cadvisor_status: string;
  prometheus_target_health: string;
  metrics_available: boolean;
  logs_available: boolean;
  node_exporter_detected: boolean;
  node_exporter_reachable: boolean;
  cadvisor_detected: boolean;
  cadvisor_running: boolean;
  docker_runtime_available: boolean;
  promtail_detected: boolean;
  promtail_reachable: boolean;
  scrape_target_health: string;
  stale_metrics: boolean;
  readiness_reasons: string[];
  remediation: string[];
  technical_details: string[];
  component_failure_reasons: Record<string, string>;
  last_validated_at: string | null;
  last_successful_check_at: string | null;
  collected_at: string;
};

export type MonitoringOverview = {
  total_servers: number;
  online_servers: number;
  offline_servers: number;
  observable_servers: number;
  degraded_servers: number;
  monitored_servers: number;
  partial_servers: number;
  unmonitored_servers: number;
  stale_servers: number;
  unknown_servers: number;
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

export type MonitoringValidation = {
  checked_servers: number;
  updated_servers: number;
  failed_servers: number;
};
