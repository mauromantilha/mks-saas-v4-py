export interface TenantDashboardDailyPoint {
  date: string;
  premium_total: number;
  commission_total: number;
}

export interface TenantDashboardMonthlyPoint {
  month: number;
  premium_total: number;
  commission_total: number;
}

export interface TenantDashboardSummary {
  tenant_code: string;
  generated_at: string;
  period: {
    as_of: string;
    year: number;
    month: number;
  };
  kpis: {
    production_premium_ytd: number;
    commission_ytd: number;
    production_premium_mtd: number;
    commission_mtd: number;
    renewals_due_next_30d: number;
    renewals_mtd: number;
    customers_total: number;
    delinquency_open_total: number;
  };
  goals: {
    sales_goal_id_mtd: number | null;
    premium_goal_mtd: number;
    commission_goal_mtd: number;
    new_customers_goal_mtd: number;
    premium_goal_ytd: number;
    commission_goal_ytd: number;
    new_customers_goal_ytd: number;
  };
  progress: {
    premium_mtd_pct: number;
    commission_mtd_pct: number;
    premium_ytd_pct: number;
    commission_ytd_pct: number;
  };
  series: {
    daily_mtd: TenantDashboardDailyPoint[];
    monthly_ytd: TenantDashboardMonthlyPoint[];
  };
}

export interface SalesGoalRecord {
  id: number;
  year: number;
  month: number;
  premium_goal: string;
  commission_goal: string;
  new_customers_goal: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface CreateSalesGoalPayload {
  year: number;
  month: number;
  premium_goal?: string | number;
  commission_goal?: string | number;
  new_customers_goal?: number;
  notes?: string;
}

export interface UpdateSalesGoalPayload {
  premium_goal?: string | number;
  commission_goal?: string | number;
  new_customers_goal?: number;
  notes?: string;
}

export interface TenantDashboardAIInsightsRequest {
  period_days?: number;
  focus?: string;
  weekly_plan?: boolean;
}

export interface TenantDashboardAIInsightsResponse {
  tenant_code: string;
  period_days: number;
  weekly_plan: boolean;
  context: Record<string, unknown>;
  insights: {
    summary: string;
    risks: string[];
    opportunities: string[];
    next_actions: string[];
    qualification_score: number | null;
    provider: string;
    generated_at: string;
    focus: string;
    [key: string]: unknown;
  };
}
