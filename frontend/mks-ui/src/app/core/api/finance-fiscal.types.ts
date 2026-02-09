export type FiscalEnvironment = "SANDBOX" | "PRODUCTION";

export interface TenantFiscalConfigRecord {
  id: number;
  provider: number;
  provider_type: string;
  provider_name: string;
  environment: FiscalEnvironment;
  auto_issue: boolean;
  active: boolean;
  has_token: boolean;
  created_at: string;
  updated_at: string;
}

export interface UpsertTenantFiscalConfigPayload {
  provider: string; // provider id or provider_type (backend accepts both)
  token?: string;
  environment: FiscalEnvironment;
  auto_issue?: boolean;
}

export type FiscalDocumentStatus =
  | "DRAFT"
  | "EMITTING"
  | "AUTHORIZED"
  | "REJECTED"
  | "CANCELLED";

export type FiscalJobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";

export interface FiscalCustomerSnapshotRecord {
  name: string;
  cpf_cnpj: string;
  address: string;
}

export interface FiscalJobSummaryRecord {
  status: FiscalJobStatus;
  attempts: number;
  next_retry_at: string | null;
  last_error: string;
}

export interface FiscalDocumentRecord {
  id: number;
  invoice_id: number;
  provider_document_id: string;
  number: string;
  series: string;
  issue_date: string | null;
  amount: string;
  status: FiscalDocumentStatus;
  xml_document_id: string;
  has_xml: boolean;
  job: FiscalJobSummaryRecord | null;
  customer_snapshot: FiscalCustomerSnapshotRecord | null;
  created_at: string;
  updated_at: string;
}

export interface RetryFiscalResponse {
  document_id: number;
  job_id: number;
  job_status: FiscalJobStatus;
  attempts: number;
  next_retry_at: string | null;
}

