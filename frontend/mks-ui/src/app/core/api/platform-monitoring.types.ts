export interface MonitoringServiceSnapshot {
  id: number;
  service_name: string;
  status: string;
  latency_ms: number;
  error_rate: number;
  metadata_json: Record<string, unknown>;
  captured_at: string;
}

export interface MonitoringTenantSnapshot {
  id: number;
  tenant_id: number;
  tenant_slug: string;
  tenant_name: string;
  last_seen_at: string | null;
  request_rate: number;
  error_rate: number;
  p95_latency: number;
  jobs_pending: number;
  captured_at: string;
}

export interface MonitoringAlert {
  id: number;
  tenant: number;
  alert_type: string;
  severity: string;
  status: string;
  message: string;
  metrics_json: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
  resolved_at: string | null;
}

export interface ControlPanelMonitoringResponse {
  period?: string;
  services: MonitoringServiceSnapshot[];
  tenants: MonitoringTenantSnapshot[];
  alerts?: MonitoringAlert[];
  summary: {
    total_services: number;
    total_tenants: number;
    degraded_tenants: number;
    open_alerts?: number;
  };
}

export interface TenantMonitoringResponse {
  period?: string;
  tenant: {
    id: number;
    legal_name: string;
    slug: string;
    status: string;
  };
  latest: MonitoringTenantSnapshot | null;
  history: MonitoringTenantSnapshot[];
  alerts?: MonitoringAlert[];
}
