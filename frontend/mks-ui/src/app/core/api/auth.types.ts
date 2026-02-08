export type TenantUserRole = "MEMBER" | "MANAGER" | "OWNER" | null;

export interface ResourceCapabilities {
  list: boolean;
  retrieve: boolean;
  create: boolean;
  update: boolean;
  partial_update: boolean;
  delete: boolean;
}

export interface TenantCapabilitiesResponse {
  tenant_code: string;
  role: TenantUserRole;
  capabilities: Record<string, ResourceCapabilities>;
}

export interface TokenResponse {
  token: string;
}

export interface TenantMeResponse {
  user_id: number;
  username: string;
  company_id: number;
  tenant_code: string;
  role: TenantUserRole;
}
