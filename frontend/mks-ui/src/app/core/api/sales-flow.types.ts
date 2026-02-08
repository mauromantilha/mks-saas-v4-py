export type LeadStatus = "NEW" | "QUALIFIED" | "DISQUALIFIED" | "CONVERTED";
export type OpportunityStage =
  | "DISCOVERY"
  | "PROPOSAL"
  | "NEGOTIATION"
  | "WON"
  | "LOST";

export interface LeadRecord {
  id: number;
  source: string;
  customer: number | null;
  status: LeadStatus;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface OpportunityRecord {
  id: number;
  customer: number;
  source_lead: number | null;
  title: string;
  stage: OpportunityStage;
  amount: string;
  expected_close_date: string | null;
  created_at: string;
  updated_at: string;
}

export type ActivityKind = "TASK" | "FOLLOW_UP" | "NOTE";
export type ActivityStatus = "PENDING" | "DONE" | "CANCELED";
export type ActivityPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export interface CommercialActivityRecord {
  id: number;
  kind: ActivityKind;
  title: string;
  description: string;
  status: ActivityStatus;
  priority: ActivityPriority;
  due_at: string | null;
  reminder_at: string | null;
  reminder_sent: boolean;
  sla_hours: number | null;
  sla_due_at: string | null;
  completed_at: string | null;
  lead: number | null;
  opportunity: number | null;
  assigned_to: number | null;
  assigned_to_username: string | null;
  created_by: number | null;
  created_by_username: string | null;
  is_overdue: boolean;
  is_sla_breached: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateCommercialActivityPayload {
  kind: ActivityKind;
  title: string;
  description?: string;
  priority?: ActivityPriority;
  due_at?: string | null;
  reminder_at?: string | null;
  sla_hours?: number | null;
  lead?: number | null;
  opportunity?: number | null;
}

export interface LeadHistoryRecord {
  lead: LeadRecord;
  activities: CommercialActivityRecord[];
  converted_opportunities: OpportunityRecord[];
}

export interface OpportunityHistoryRecord {
  opportunity: OpportunityRecord;
  activities: CommercialActivityRecord[];
}

export interface SalesMetricsRecord {
  tenant_code: string;
  lead_funnel: Record<LeadStatus, number>;
  opportunity_funnel: Record<OpportunityStage, number>;
  activities: {
    open_total: number;
    overdue_total: number;
    due_today_total: number;
    reminders_due_total: number;
    sla_breached_total: number;
  };
  conversion: {
    lead_to_opportunity_rate: number;
    opportunity_win_rate: number;
  };
}
