export type TenantStatus = "ACTIVE" | "SUSPENDED" | "CANCELLED" | "DELETED";
export type ContractStatus = "DRAFT" | "SENT" | "SIGNED" | "CANCELLED";
export type PlanTier = "STARTER" | "GROWTH" | "ENTERPRISE";

export interface TenantListParams {
  status?: TenantStatus | "";
  plan?: number | null;
  trial?: boolean | "";
  search?: string;
  page?: number;
  page_size?: number;
}

export interface PaginatedResponseDto<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface TenantPlanSummaryDto {
  id: number;
  name: string;
  tier: PlanTier;
}

export interface TenantSubscriptionSummaryDto {
  id: number;
  plan: TenantPlanSummaryDto | null;
  start_date?: string | null;
  end_date?: string | null;
  is_trial: boolean;
  trial_ends_at: string | null;
  is_courtesy?: boolean;
  setup_fee_override?: string | null;
  status: string;
}

export interface TenantDto {
  id: number;
  legal_name: string;
  cnpj: string;
  contact_email: string;
  slug: string;
  subdomain: string;
  cep: string;
  street: string;
  number: string;
  complement: string;
  district: string;
  city: string;
  state: string;
  status: TenantStatus;
  created_at: string;
  updated_at: string;
  subscription?: TenantSubscriptionSummaryDto | null;
  plan_name?: string | null;
  trial_ends_at?: string | null;
  is_trial?: boolean;
}

export interface TenantListResponseDto {
  items: TenantDto[];
  total: number;
  page: number;
  page_size: number;
}

export interface TenantCreateDto {
  legal_name: string;
  cnpj?: string;
  contact_email?: string;
  slug: string;
  subdomain: string;
  cep?: string;
  street?: string;
  number?: string;
  complement?: string;
  district?: string;
  city?: string;
  state?: string;
  status?: TenantStatus;
}

export interface TenantUpdateDto extends Partial<TenantCreateDto> {}

export interface TenantStatusChangeDto {
  reason?: string;
}

export interface TenantDeleteDto extends TenantStatusChangeDto {
  confirm_text: string;
}

export interface CepLookupResponseDto {
  cep: string;
  logradouro: string;
  bairro: string;
  cidade: string;
  uf: string;
}

export interface PlanDto {
  id: number;
  name: string;
  tier: PlanTier;
  is_active: boolean;
  price: {
    monthly_price: string;
    setup_fee: string;
  } | null;
}

export interface TenantSubscriptionUpdateDto {
  plan_id: number;
  is_trial: boolean;
  trial_days?: number;
  is_courtesy?: boolean;
  setup_fee_override?: string | null;
}

export interface ContractEmailLogDto {
  id: number;
  to_email: string;
  resend_message_id: string;
  status: string;
  error: string;
  sent_at: string;
}

export interface ContractDto {
  id: number;
  tenant: number;
  status: ContractStatus;
  contract_version: number;
  snapshot_json: Record<string, unknown>;
  pdf_document_id: string | null;
  created_at: string;
  email_logs?: ContractEmailLogDto[];
}

export interface SendContractDto {
  to_email: string;
  force_send?: boolean;
}

export interface FeatureFlagDto {
  id: number;
  key: string;
  name: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantFeatureFlagDto {
  id: number | null;
  tenant: number;
  feature: FeatureFlagDto;
  enabled: boolean;
  updated_by: number | null;
  updated_by_username: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface TenantFeatureFlagUpdateDto {
  feature_key: string;
  enabled: boolean;
}

export type TenantIntegrationProvider = "SMTP" | "WHATSAPP" | "VERTEX_AI" | "CUSTOM";

export interface TenantOperationalSettingsDto {
  tenant: number;
  requests_per_minute: number;
  storage_limit_gb: string;
  docs_storage_limit_gb: string;
  module_limits_json: Record<string, unknown>;
  current_storage_gb: string;
  current_docs_storage_gb: string;
  last_storage_sync_at: string | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface TenantOperationalSettingsUpdateDto {
  requests_per_minute?: number;
  storage_limit_gb?: string;
  docs_storage_limit_gb?: string;
  module_limits_json?: Record<string, unknown>;
  current_storage_gb?: string;
  current_docs_storage_gb?: string;
  last_storage_sync_at?: string | null;
}

export interface TenantIntegrationSecretRefDto {
  id: number;
  tenant: number;
  provider: TenantIntegrationProvider;
  alias: string;
  secret_manager_ref: string;
  metadata_json: Record<string, unknown>;
  is_active: boolean;
  created_by: number | null;
  created_by_username: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantIntegrationSecretRefUpsertDto {
  provider: TenantIntegrationProvider;
  alias: string;
  secret_manager_ref: string;
  metadata_json?: Record<string, unknown>;
  is_active?: boolean;
}

export interface TenantReleaseRecordDto {
  id: number;
  tenant: number;
  backend_version: string;
  frontend_version: string;
  git_sha: string;
  source: string;
  changelog: string;
  changelog_json: unknown;
  is_current: boolean;
  created_by: number | null;
  created_by_username: string | null;
  deployed_at: string;
  created_at: string;
}

export interface TenantReleaseRecordCreateDto {
  backend_version: string;
  frontend_version?: string;
  git_sha?: string;
  source?: string;
  changelog?: string;
  changelog_json?: unknown;
  deployed_at?: string;
  is_current?: boolean;
}

export interface TenantInternalNoteDto {
  id: number;
  tenant: number;
  note: string;
  created_by: number | null;
  created_by_username: string | null;
  created_at: string;
}

export interface TenantInternalNoteCreateDto {
  note: string;
}

export interface GlobalMonitoringParams {
  period?: string;
  page?: number;
  page_size?: number;
}

export interface TenantMonitoringParams {
  period?: string;
  page?: number;
  page_size?: number;
}

export interface MonitoringServiceSnapshotDto {
  id: number;
  service_name: string;
  status: string;
  latency_ms: number;
  error_rate: number;
  metadata_json: Record<string, unknown>;
  captured_at: string;
}

export interface MonitoringTenantSnapshotDto {
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

export interface MonitoringAlertDto {
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

export interface GlobalMonitoringDto {
  period?: string;
  services: MonitoringServiceSnapshotDto[];
  tenants: MonitoringTenantSnapshotDto[];
  alerts?: MonitoringAlertDto[];
  summary: {
    total_services: number;
    total_tenants: number;
    degraded_tenants: number;
    open_alerts?: number;
    registered_tenants?: number;
    active_tenants?: number;
    suspended_tenants?: number;
    deleted_tenants?: number;
    request_traffic?: number;
    logged_in_users?: number;
    cloud_run_status?: string;
    cloud_run_services?: number;
    database_status?: string;
    database_count?: number;
    storage_status?: string;
    storage_buckets?: number;
    most_accessed_pages?: Array<string | { path?: string; count?: number }>;
  };
}

export interface TenantMonitoringDto {
  period?: string;
  tenant: {
    id: number;
    legal_name: string;
    slug: string;
    status: string;
  };
  latest: MonitoringTenantSnapshotDto | null;
  history: MonitoringTenantSnapshotDto[];
  alerts?: MonitoringAlertDto[];
}

export interface AuditEventDto {
  id: number;
  actor: number | null;
  actor_username: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  target_tenant: number | null;
  target_tenant_slug: string | null;
  before_data: Record<string, unknown>;
  after_data: Record<string, unknown>;
  correlation_id: string;
  created_at: string;
}

export interface AuditListParams {
  page?: number;
  page_size?: number;
  period?: string;
  date_from?: string;
  date_to?: string;
  action?: string;
  entity_type?: string;
  actor?: number | string;
  tenant_id?: number;
  search?: string;
}
