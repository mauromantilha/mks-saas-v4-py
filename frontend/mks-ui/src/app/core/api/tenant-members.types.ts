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

export interface TenantProducer {
  id: number;
  membership_id: number;
  user_id: number;
  username: string;
  email: string;
  role: MembershipRole;
  membership_is_active: boolean;
  full_name: string;
  cpf: string;
  team_name: string;
  is_team_manager: boolean;
  zip_code: string;
  state: string;
  city: string;
  neighborhood: string;
  street: string;
  street_number: string;
  address_complement: string;
  commission_transfer_percent: string;
  payout_hold_days: number;
  bank_code: string;
  bank_name: string;
  bank_agency: string;
  bank_account: string;
  bank_account_type: string;
  pix_key_type: string;
  pix_key: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantProducersListResponse {
  tenant_code: string;
  results: TenantProducer[];
}

export interface TenantProducerUpsertPayload {
  username?: string;
  email?: string;
  role: MembershipRole;
  is_active?: boolean;
  full_name: string;
  cpf: string;
  team_name?: string;
  is_team_manager?: boolean;
  zip_code?: string;
  state?: string;
  city?: string;
  neighborhood?: string;
  street?: string;
  street_number?: string;
  address_complement?: string;
  commission_transfer_percent: string | number;
  payout_hold_days?: number;
  bank_code?: string;
  bank_name?: string;
  bank_agency?: string;
  bank_account?: string;
  bank_account_type?: string;
  pix_key_type?: string;
  pix_key?: string;
}

export interface TenantProducerPatchPayload extends Partial<TenantProducerUpsertPayload> {}

export interface BankCatalogItem {
  code: string;
  name: string;
}

export interface BankCatalogResponse {
  results: BankCatalogItem[];
}

export interface TeamVsGoalSummary {
  company_goal_commission: string;
  team_result_current_month: string;
  target_per_producer: string;
  progress_pct: number;
  producer_count: number;
}

export interface TenantProducerPerformanceResult {
  producer_id: number;
  membership_id: number;
  user_id: number;
  username: string;
  full_name: string;
  role: MembershipRole;
  team_name: string;
  is_team_manager: boolean;
  commission_transfer_percent: string;
  result_current_month: string;
}

export interface TenantProducerTeamPerformance {
  team_name: string;
  manager: string | null;
  result_current_month: string;
  members: TenantProducerPerformanceResult[];
}

export interface TenantProducerPerformanceResponse {
  period: {
    month: number;
    year: number;
    start_date: string;
    end_date_exclusive: string;
  };
  team_vs_goal: TeamVsGoalSummary;
  individual_results: TenantProducerPerformanceResult[];
  teams: TenantProducerTeamPerformance[];
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
