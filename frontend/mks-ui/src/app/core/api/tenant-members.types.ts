export type MembershipRole = "MEMBER" | "MANAGER" | "OWNER";

export interface TenantMember {
  id: number;
  user_id: number;
  username: string;
  email: string;
  role: MembershipRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantMembersListResponse {
  tenant_code: string;
  results: TenantMember[];
}

export interface TenantMemberUpsertPayload {
  username: string;
  role: MembershipRole;
  is_active?: boolean;
}

export interface TenantMemberPatchPayload {
  role?: MembershipRole;
  is_active?: boolean;
}
