export type TenantRole = "MEMBER" | "MANAGER" | "OWNER";

export type HttpMethod =
  | "GET"
  | "HEAD"
  | "OPTIONS"
  | "POST"
  | "PUT"
  | "PATCH"
  | "DELETE";

export type TenantResource =
  | "customers"
  | "leads"
  | "opportunities"
  | "activities"
  | "metrics"
  | "apolices"
  | "endossos";

export type RoleMatrix = Partial<Record<HttpMethod, TenantRole[]>>;

export type TenantRbacOverrides = Partial<Record<TenantResource, RoleMatrix>>;

export interface TenantRbacResponse {
  tenant_code: string;
  rbac_overrides: TenantRbacOverrides;
  effective_role_matrices: Record<TenantResource, RoleMatrix>;
}
