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
  title: string;
  stage: OpportunityStage;
  amount: string;
  expected_close_date: string | null;
  created_at: string;
  updated_at: string;
}
