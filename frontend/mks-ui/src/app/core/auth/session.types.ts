import { TenantUserRole } from "../api/auth.types";

export interface UserSession {
  token: string;
  tenantCode: string;
  username: string;
  role: TenantUserRole;
  platformAdmin: boolean;
}
