export type LedgerScope = "TENANT" | "PLATFORM";
export type LedgerAction = "CREATE" | "UPDATE" | "DELETE" | "SYSTEM";

export interface LedgerEntry {
  id: number;
  scope: LedgerScope;
  company_id: number | null;
  actor_username: string;
  actor_email: string;
  action: LedgerAction;
  event_type: string;
  resource_label: string;
  resource_pk: string;
  occurred_at: string;
  request_id: string;
  request_method: string;
  request_path: string;
  ip_address: string | null;
  user_agent: string;
  chain_id: string;
  prev_hash: string;
  entry_hash: string;
  data_before: unknown;
  data_after: unknown;
  metadata: unknown;
}

