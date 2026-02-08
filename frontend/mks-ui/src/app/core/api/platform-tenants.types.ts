export type TenantPlan = "STARTER" | "PRO" | "ENTERPRISE";
export type ContractStatus = "TRIAL" | "ACTIVE" | "SUSPENDED" | "CANCELED";
export type IsolationModel = "SHARED_SCHEMA" | "DATABASE_PER_TENANT";
export type ProvisioningStatus = "PENDING" | "PROVISIONING" | "READY" | "FAILED";

export interface PlatformTenantContract {
  plan: TenantPlan;
  status: ContractStatus;
  seats: number;
  monthly_fee: string;
  start_date: string;
  end_date: string | null;
  auto_renew: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface PlatformTenantProvisioning {
  isolation_model: IsolationModel;
  status: ProvisioningStatus;
  database_alias: string;
  database_name: string;
  database_host: string;
  database_port: number;
  database_user: string;
  database_password_secret: string;
  portal_url: string;
  provisioned_at: string | null;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface PlatformTenantRecord {
  id: number;
  name: string;
  tenant_code: string;
  subdomain: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  contract: PlatformTenantContract | null;
  provisioning: PlatformTenantProvisioning | null;
}

export interface CreatePlatformTenantPayload {
  name: string;
  tenant_code: string;
  subdomain: string;
  is_active?: boolean;
  contract?: {
    plan?: TenantPlan;
    status?: ContractStatus;
    seats?: number;
    monthly_fee?: string;
  };
  provisioning?: {
    database_alias?: string;
    database_name?: string;
    database_user?: string;
  };
}

export interface ProvisionTenantPayload {
  status: ProvisioningStatus;
  portal_url?: string;
  last_error?: string;
}
