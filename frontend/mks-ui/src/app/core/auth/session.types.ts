import { TenantUserRole } from "../api/auth.types";

export type SessionPortalType = "CONTROL_PLANE" | "TENANT";

export interface UserSession {
  token: string;
  tenantCode: string | null;
  username: string;
  role: TenantUserRole;
  platformAdmin: boolean;
  portalType: SessionPortalType;
}
