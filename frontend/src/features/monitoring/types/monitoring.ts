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
  collected_at: string;
};

export type MonitoringOverview = {
  total_servers: number;
  online_servers: number;
  offline_servers: number;
  servers: ServerMetrics[];
};

export type PrometheusHealth = {
  configured: boolean;
  reachable: boolean;
  error: string | null;
};
