export type TenantStatus = "ACTIVE" | "SUSPENDED" | "CANCELLED" | "DELETED";
export type PlanTier = "STARTER" | "GROWTH" | "ENTERPRISE";

export interface PlatformTenantRecord {
  id: number;
  company_id: number;
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
  last_status_reason: string;
  last_status_changed_at: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
  subscription: TenantSubscriptionRecord | null;
  limits?: TenantOperationalSettingsRecord | null;
  current_release?: TenantReleaseRecord | null;
  open_alerts_count?: number;
}

export interface PlanRecord {
  id: number;
  name: string;
  tier: PlanTier;
  is_active: boolean;
  price: {
    monthly_price: string;
    setup_fee: string;
  } | null;
}

export interface TenantSubscriptionRecord {
  id: number;
  plan: PlanRecord;
  start_date: string;
  end_date: string | null;
  is_trial: boolean;
  trial_ends_at: string | null;
  is_courtesy: boolean;
  setup_fee_override: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CreatePlatformTenantPayload {
  legal_name: string;
  cnpj?: string;
  contact_email?: string;
  slug: string;
  subdomain: string;
  cep?: string;
  street?: string;
  district?: string;
  city?: string;
  state?: string;
  status?: TenantStatus;
  subscription?: {
    plan_id: number;
    is_trial: boolean;
    trial_days?: number;
    is_courtesy: boolean;
    setup_fee_override?: string | null;
  };
}

export interface PlanPayload {
  name: string;
  tier: PlanTier;
  is_active: boolean;
  monthly_price: string;
  setup_fee: string;
}

export interface TenantSubscriptionPayload {
  plan_id: number;
  is_trial: boolean;
  trial_days?: number;
  is_courtesy: boolean;
  setup_fee_override?: string | null;
}

export interface TenantListFilters {
  status?: TenantStatus | "";
  planId?: number | null;
  trial?: "" | "true" | "false";
  search?: string;
}

export interface AdminAuditEventRecord {
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

export interface TenantInternalNoteRecord {
  id: number;
  tenant: number;
  note: string;
  created_by: number | null;
  created_by_username: string | null;
  created_at: string;
}

export interface FeatureFlagRecord {
  id: number;
  key: string;
  name: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantFeatureFlagRecord {
  id: number | null;
  tenant: number;
  feature: FeatureFlagRecord;
  enabled: boolean;
  updated_by: number | null;
  updated_by_username: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ContractEmailLogRecord {
  id: number;
  to_email: string;
  resend_message_id: string;
  status: string;
  error: string;
  sent_at: string;
}

export interface TenantContractRecord {
  id: number;
  tenant: number;
  status: "DRAFT" | "SENT" | "SIGNED" | "CANCELLED";
  contract_version: number;
  snapshot_json: Record<string, unknown>;
  pdf_document_id: string | null;
  created_at: string;
  email_logs?: ContractEmailLogRecord[];
  email_log?: ContractEmailLogRecord;
}

export interface TenantOperationalSettingsRecord {
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

export interface TenantIntegrationSecretRefRecord {
  id: number;
  tenant: number;
  provider: "RESEND" | "WHATSAPP" | "VERTEX_AI" | "CUSTOM";
  alias: string;
  secret_manager_ref: string;
  metadata_json: Record<string, unknown>;
  is_active: boolean;
  created_by: number | null;
  created_by_username: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantAlertEventRecord {
  id: number;
  tenant: number;
  alert_type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  status: "OPEN" | "RESOLVED";
  message: string;
  metrics_json: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
  resolved_at: string | null;
}

export interface TenantReleaseRecord {
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

export interface TenantImpersonationSessionRecord {
  id: number;
  actor: number;
  actor_username: string;
  tenant: number;
  status: "ACTIVE" | "ENDED" | "EXPIRED";
  reason: string;
  correlation_id: string;
  started_at: string;
  expires_at: string;
  ended_at: string | null;
}
