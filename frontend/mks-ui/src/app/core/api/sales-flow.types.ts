export type LeadStatus = "NEW" | "QUALIFIED" | "DISQUALIFIED" | "CONVERTED";
export type CustomerType = "INDIVIDUAL" | "COMPANY";
export type CustomerLifecycleStage = "LEAD" | "PROSPECT" | "CUSTOMER" | "INACTIVE";
export type OpportunityStage =
  | "NEW"
  | "QUALIFICATION"
  | "NEEDS_ASSESSMENT"
  | "QUOTATION"
  | "DISCOVERY"
  | "PROPOSAL"
  | "PROPOSAL_PRESENTATION"
  | "NEGOTIATION"
  | "WON"
  | "LOST";

export interface CustomerContactRecord {
  id: number;
  name: string;
  email: string;
  phone: string;
  role: string;
  is_primary: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface CreateCustomerContactPayload {
  id?: number;
  name: string;
  email?: string;
  phone?: string;
  role?: string;
  is_primary?: boolean;
  notes?: string;
}

export interface CustomerRecord {
  id: number;
  name: string;
  email: string;
  customer_type: CustomerType;
  lifecycle_stage: CustomerLifecycleStage;
  legal_name: string;
  trade_name: string;
  phone: string;
  whatsapp: string;
  document: string;
  cnpj: string;
  cpf: string;
  state_registration: string;
  municipal_registration: string;
  website: string;
  linkedin_url: string;
  instagram_url: string;
  facebook_url: string;
  lead_source: string;
  industry: string;
  company_size: string;
  annual_revenue: string | null;
  contact_name: string;
  contact_role: string;
  secondary_contact_name: string;
  secondary_contact_email: string;
  secondary_contact_phone: string;
  billing_email: string;
  billing_phone: string;
  zip_code: string;
  state: string;
  city: string;
  neighborhood: string;
  street: string;
  street_number: string;
  address_complement: string;
  contacts?: CustomerContactRecord[];
  assigned_to: number | null;
  assigned_to_username: string | null;
  last_contact_at: string | null;
  next_follow_up_at: string | null;
  notes: string;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateCustomerPayload {
  name: string;
  email: string;
  customer_type?: CustomerType;
  lifecycle_stage?: CustomerLifecycleStage;
  document?: string;
  cnpj?: string;
  cpf?: string;
  phone?: string;
  whatsapp?: string;
  zip_code?: string;
  state?: string;
  city?: string;
  neighborhood?: string;
  street?: string;
  street_number?: string;
  address_complement?: string;
  contact_name?: string;
  industry?: string;
  lead_source?: string;
  notes?: string;
  contacts?: CreateCustomerContactPayload[];
}

export interface CepLookupResponse {
  zip_code: string;
  street: string;
  neighborhood: string;
  city: string;
  state: string;
  provider: string;
}

export interface LeadRecord {
  id: number;
  source: string;
  capture_channel?: string;
  external_id?: string;
  external_campaign?: string;
  full_name: string;
  job_title: string;
  company_name: string;
  email: string;
  phone: string;
  whatsapp: string;
  cnpj: string;
  website: string;
  linkedin_url: string;
  instagram_url: string;
  lead_score_label?: string;
  product_line?: string;
  cnae_code?: string;
  company_size_estimate?: string;
  raw_payload?: Record<string, unknown>;
  needs_summary?: string;
  needs_payload?: Record<string, unknown>;
  first_response_sla_minutes?: number;
  first_response_due_at?: string | null;
  first_response_at?: string | null;
  customer: number | null;
  status: LeadStatus;
  products_of_interest: string;
  estimated_budget: string | null;
  estimated_close_date: string | null;
  qualification_score: number | null;
  disqualification_reason: string;
  last_contact_at: string | null;
  next_follow_up_at: string | null;
  notes: string;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateLeadPayload {
  source: string;
  capture_channel?: string;
  external_id?: string;
  external_campaign?: string;
  full_name?: string;
  job_title?: string;
  company_name?: string;
  email?: string;
  phone?: string;
  whatsapp?: string;
  cnpj?: string;
  website?: string;
  linkedin_url?: string;
  instagram_url?: string;
  products_of_interest?: string;
  estimated_budget?: string | number;
  notes?: string;
}

export interface UpdateLeadPayload {
  status?: LeadStatus;
  disqualification_reason?: string;
  notes?: string;
  next_follow_up_at?: string | null;
  last_contact_at?: string | null;
}

export interface CreateOpportunityPayload {
  customer: number;
  title: string;
  stage?: OpportunityStage;
  product_line?: string;
  amount?: string | number;
  expected_close_date?: string | null;
  closing_probability?: number;
  notes?: string;
}

export interface OpportunityRecord {
  id: number;
  customer: number;
  source_lead: number | null;
  title: string;
  stage: OpportunityStage;
  product_line: string;
  amount: string;
  expected_close_date: string | null;
  closing_probability: number;
  next_step: string;
  next_step_due_at: string | null;
  needs_payload: Record<string, unknown>;
  quote_payload: Record<string, unknown>;
  proposal_pdf_url: string;
  proposal_tracking_token: string;
  proposal_sent_at: string | null;
  proposal_viewed_at: string | null;
  loss_reason: string;
  competitors: string;
  handover_notes: string;
  notes: string;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PolicyRequestRecord {
  id: number;
  opportunity: number;
  customer: number;
  source_lead: number | null;
  product_line: string;
  status:
    | "PENDING_DATA"
    | "UNDER_REVIEW"
    | "READY_TO_ISSUE"
    | "ISSUED"
    | "REJECTED";
  inspection_required: boolean;
  inspection_status:
    | "NOT_REQUIRED"
    | "PENDING"
    | "SCHEDULED"
    | "APPROVED"
    | "REJECTED";
  inspection_scheduled_at: string | null;
  inspection_notes: string;
  billing_method: "BANK_DEBIT" | "INVOICE" | "PIX" | "CREDIT_CARD" | "OTHER" | "";
  bank_account_holder: string;
  bank_name: string;
  bank_branch: string;
  bank_account: string;
  bank_document: string;
  payment_day: number | null;
  final_premium: string | null;
  final_commission: string | null;
  issue_deadline_at: string | null;
  issued_at: string | null;
  notes: string;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProposalOptionRecord {
  id: number;
  opportunity: number;
  insurer_name: string;
  plan_name: string;
  coverage_summary: string;
  deductible: string;
  annual_premium: string | null;
  monthly_premium: string | null;
  franchise_notes: string;
  commission_percent: string | null;
  commission_amount: string | null;
  ranking_score: number;
  is_recommended: boolean;
  external_reference: string;
  notes: string;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreatePolicyRequestPayload {
  opportunity: number;
  customer?: number;
  source_lead?: number | null;
  product_line?: string;
  inspection_required?: boolean;
  issue_deadline_at?: string | null;
  notes?: string;
}

export interface UpdatePolicyRequestPayload {
  status?:
    | "PENDING_DATA"
    | "UNDER_REVIEW"
    | "READY_TO_ISSUE"
    | "ISSUED"
    | "REJECTED";
  inspection_required?: boolean;
  inspection_status?: "NOT_REQUIRED" | "PENDING" | "SCHEDULED" | "APPROVED" | "REJECTED";
  inspection_scheduled_at?: string | null;
  inspection_notes?: string;
  billing_method?: "BANK_DEBIT" | "INVOICE" | "PIX" | "CREDIT_CARD" | "OTHER" | "";
  bank_account_holder?: string;
  bank_name?: string;
  bank_branch?: string;
  bank_account?: string;
  bank_document?: string;
  payment_day?: number | null;
  final_premium?: string | number | null;
  final_commission?: string | number | null;
  issue_deadline_at?: string | null;
  notes?: string;
}

export interface CreateProposalOptionPayload {
  opportunity: number;
  insurer_name: string;
  plan_name?: string;
  coverage_summary?: string;
  annual_premium?: string | number | null;
  monthly_premium?: string | number | null;
  commission_percent?: string | number | null;
  commission_amount?: string | number | null;
  ranking_score?: number;
  is_recommended?: boolean;
  notes?: string;
}

export type ActivityKind = "TASK" | "FOLLOW_UP" | "NOTE";
export type ActivityStatus = "PENDING" | "DONE" | "CANCELED";
export type ActivityPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export type ActivityChannel =
  | "EMAIL"
  | "PHONE"
  | "WHATSAPP"
  | "MEETING"
  | "VISIT"
  | "LINKEDIN"
  | "OTHER";
export type ActivityOutcome =
  | "CONNECTED"
  | "NO_ANSWER"
  | "INTERESTED"
  | "NOT_INTERESTED"
  | "FOLLOW_UP_SCHEDULED"
  | "PROPOSAL_SENT"
  | "CLOSED_WON"
  | "CLOSED_LOST";

export interface CommercialActivityRecord {
  id: number;
  kind: ActivityKind;
  title: string;
  description: string;
  channel: ActivityChannel;
  outcome: ActivityOutcome | "";
  status: ActivityStatus;
  priority: ActivityPriority;
  due_at: string | null;
  reminder_at: string | null;
  reminder_sent: boolean;
  sla_hours: number | null;
  sla_due_at: string | null;
  completed_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_minutes: number | null;
  meeting_url: string;
  location: string;
  lead: number | null;
  opportunity: number | null;
  assigned_to: number | null;
  assigned_to_username: string | null;
  created_by: number | null;
  created_by_username: string | null;
  is_overdue: boolean;
  is_sla_breached: boolean;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateCommercialActivityPayload {
  kind: ActivityKind;
  title: string;
  description?: string;
  channel?: ActivityChannel;
  outcome?: ActivityOutcome | "";
  priority?: ActivityPriority;
  due_at?: string | null;
  reminder_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  meeting_url?: string;
  location?: string;
  sla_hours?: number | null;
  lead?: number | null;
  opportunity?: number | null;
}

export interface LeadConvertPayload {
  customer?: number | null;
  title?: string;
  stage?: Extract<
    OpportunityStage,
    | "NEW"
    | "QUALIFICATION"
    | "NEEDS_ASSESSMENT"
    | "QUOTATION"
    | "PROPOSAL_PRESENTATION"
    | "NEGOTIATION"
  >;
  amount?: string | number;
  expected_close_date?: string | null;
  create_customer_if_missing?: boolean;
  create_policy_request?: boolean;
}

export interface LeadConvertResponse {
  lead: LeadRecord;
  customer: CustomerRecord;
  customer_created: boolean;
  opportunity: OpportunityRecord;
  policy_request: PolicyRequestRecord | null;
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

export interface AIInsightsRequestPayload {
  focus?: string;
  include_cnpj_enrichment?: boolean;
}

export interface CommercialInsightsPayload {
  summary: string;
  risks: string[];
  opportunities: string[];
  next_actions: string[];
  qualification_score: number | null;
  provider: string;
  generated_at: string;
  focus: string;
  provider_errors?: string[];
  [key: string]: unknown;
}

export interface AIInsightResponse {
  tenant_code: string;
  entity_type: string;
  entity_id: number;
  insights: CommercialInsightsPayload;
  cnpj_profile: Record<string, unknown> | null;
  updated_fields: string[];
}

export interface CNPJEnrichmentResponse {
  tenant_code: string;
  entity_id: number;
  cnpj_profile: Record<string, unknown>;
  updated_fields: string[];
}

export interface SalesMetricsFilters {
  from?: string;
  to?: string;
  assigned_to?: string;
}

export interface SalesMetricsRecord {
  tenant_code: string;
  period: {
    from_date: string | null;
    to_date: string | null;
    assigned_to_user_id: number | null;
  };
  lead_funnel: Record<LeadStatus, number>;
  opportunity_funnel: Record<OpportunityStage, number>;
  policy_requests: {
    PENDING_DATA: number;
    UNDER_REVIEW: number;
    READY_TO_ISSUE: number;
    ISSUED: number;
    REJECTED: number;
  };
  activities: {
    open_total: number;
    overdue_total: number;
    due_today_total: number;
    reminders_due_total: number;
    sla_breached_total: number;
  };
  activities_by_priority: {
    LOW: number;
    MEDIUM: number;
    HIGH: number;
    URGENT: number;
  };
  pipeline_value: {
    open_total_amount: number;
    won_total_amount: number;
    lost_total_amount: number;
    expected_close_next_30d_amount: number;
  };
  conversion: {
    lead_to_opportunity_rate: number;
    opportunity_win_rate: number;
  };
}
