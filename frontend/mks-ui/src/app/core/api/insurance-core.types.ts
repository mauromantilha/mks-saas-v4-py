export type InsurerStatus = "ACTIVE" | "INACTIVE";
export type InsurerIntegrationType = "NONE" | "API" | "MANUAL" | "BROKER_PORTAL";

export interface InsurerRecord {
  id: number;
  name: string;
  legal_name: string;
  cnpj: string;
  status: InsurerStatus;
  integration_type: InsurerIntegrationType;
  integration_config: Record<string, unknown>;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateInsurerPayload {
  name: string;
  legal_name?: string;
  cnpj?: string;
  status?: InsurerStatus;
  integration_type?: InsurerIntegrationType;
  integration_config?: Record<string, unknown>;
}

export interface UpdateInsurerPayload {
  name?: string;
  legal_name?: string;
  cnpj?: string;
  status?: InsurerStatus;
  integration_type?: InsurerIntegrationType;
  integration_config?: Record<string, unknown>;
}

