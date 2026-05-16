import { apiClient } from '../../../lib/api/client';
import type { MonitoringOverview, PrometheusHealth, ServerMetrics } from '../types/monitoring';

export async function getMonitoringOverview(): Promise<MonitoringOverview> {
  const response = await apiClient.get<MonitoringOverview>('/monitoring/overview');
  return response.data;
}

export async function getPrometheusHealth(): Promise<PrometheusHealth> {
  const response = await apiClient.get<PrometheusHealth>('/monitoring/prometheus/health');
  return response.data;
}

export async function getServerMetrics(serverId: string): Promise<ServerMetrics> {
  const response = await apiClient.get<ServerMetrics>(`/monitoring/servers/${serverId}/metrics`);
  return response.data;
}
