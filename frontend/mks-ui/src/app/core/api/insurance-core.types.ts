export type InsurerStatus = "ACTIVE" | "INACTIVE";
export type InsurerIntegrationType = "NONE" | "API" | "MANUAL" | "BROKER_PORTAL";

export type InsuranceProductStatus = "ACTIVE" | "INACTIVE";
export type LineOfBusiness =
  | "AUTO"
  | "LIFE"
  | "HEALTH"
  | "PROPERTY"
  | "TRANSPORT"
  | "LIABILITY"
  | "OTHER";

export type CoverageType = "BASIC" | "ADDITIONAL" | "ASSIST";

export type PolicyStatus =
  | "DRAFT"
  | "UNDERWRITING"
  | "ISSUED"
  | "ACTIVE"
  | "EXPIRED"
  | "CANCELLED";

export type PolicyItemType = "AUTO" | "PROPERTY" | "LIFE" | "OTHER";

export type PolicyDocumentRequirementStatus =
  | "PENDING"
  | "RECEIVED"
  | "VALIDATED"
  | "REJECTED";

export type EndorsementType =
  | "COVERAGE_CHANGE"
  | "INSURED_OBJECT_CHANGE"
  | "FINANCIAL_CHANGE"
  | "CANCELLATION_LIKE";

export type EndorsementStatus = "DRAFT" | "ISSUED" | "APPLIED" | "CANCELLED";

export interface InsurerRecord {
  id: number;
  name: string;
  legal_name: string;
  cnpj: string;
  zip_code: string;
  state: string;
  city: string;
  neighborhood: string;
  street: string;
  street_number: string;
  address_complement: string;
  contacts?: InsurerContactRecord[];
  status: InsurerStatus;
  integration_type: InsurerIntegrationType;
  integration_config: Record<string, unknown>;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface InsurerContactRecord {
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

export interface CreateInsurerContactPayload {
  id?: number;
  name: string;
  email?: string;
  phone?: string;
  role?: string;
  is_primary?: boolean;
  notes?: string;
}

export interface CreateInsurerPayload {
  name: string;
  legal_name?: string;
  cnpj?: string;
  zip_code?: string;
  state?: string;
  city?: string;
  neighborhood?: string;
  street?: string;
  street_number?: string;
  address_complement?: string;
  contacts?: CreateInsurerContactPayload[];
  status?: InsurerStatus;
  integration_type?: InsurerIntegrationType;
  integration_config?: Record<string, unknown>;
}

export interface UpdateInsurerPayload {
  name?: string;
  legal_name?: string;
  cnpj?: string;
  zip_code?: string;
  state?: string;
  city?: string;
  neighborhood?: string;
  street?: string;
  street_number?: string;
  address_complement?: string;
  contacts?: CreateInsurerContactPayload[];
  status?: InsurerStatus;
  integration_type?: InsurerIntegrationType;
  integration_config?: Record<string, unknown>;
}

export interface CepLookupResponse {
  zip_code: string;
  street: string;
  neighborhood: string;
  city: string;
  state: string;
  provider: string;
}

export interface InsuranceProductRecord {
  id: number;
  insurer: { id: number; name: string };
  code: string;
  name: string;
  line_of_business: LineOfBusiness;
  status: InsuranceProductStatus;
  rules: Record<string, unknown>;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProductCoverageRecord {
  id: number;
  product: { id: number; name: string };
  code: string;
  name: string;
  coverage_type: CoverageType;
  default_limit_amount: string;
  default_deductible_amount: string;
  required: boolean;
  ai_insights: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PolicyRecord {
  id: number;
  policy_number: string | null;
  insurer: { id: number; name: string };
  product: { id: number; name: string; line_of_business: LineOfBusiness };
  insured_party_id: number;
  insured_party_label: string;
  broker_reference: string;
  status: PolicyStatus;
  issue_date: string | null;
  start_date: string;
  end_date: string;
  currency: string;
  premium_total: string;
  tax_total: string;
  commission_total: string | null;
  notes: string;
  ai_insights: Record<string, unknown>;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface CreatePolicyPayload {
  policy_number?: string | null;
  insurer_id: number;
  product_id: number;
  insured_party_id: number;
  broker_reference?: string;
  start_date: string;
  end_date: string;
  issue_date?: string | null;
  currency?: string;
  premium_total?: string;
  tax_total?: string;
  commission_total?: string | null;
  notes?: string;
}

export interface UpdatePolicyPayload {
  policy_number?: string | null;
  insurer_id?: number;
  product_id?: number;
  insured_party_id?: number;
  broker_reference?: string;
  start_date?: string;
  end_date?: string;
  issue_date?: string | null;
  currency?: string;
  premium_total?: string;
  tax_total?: string;
  commission_total?: string | null;
  notes?: string;
}

export interface TransitionPolicyPayload {
  status: PolicyStatus;
  reason?: string;
}

export interface PolicyItemRecord {
  id: number;
  policy: { id: number; policy_number: string | null };
  item_type: PolicyItemType;
  description: string;
  attributes: Record<string, unknown>;
  sum_insured: string;
  created_at: string;
  updated_at: string;
}

export interface CreatePolicyItemPayload {
  policy_id: number;
  item_type: PolicyItemType;
  description?: string;
  attributes?: Record<string, unknown>;
  sum_insured?: string;
}

export interface PolicyCoverageRecord {
  id: number;
  policy: { id: number; policy_number: string | null };
  product_coverage: { id: number; code: string; name: string };
  limit_amount: string;
  deductible_amount: string;
  premium_amount: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreatePolicyCoveragePayload {
  policy_id: number;
  product_coverage_id: number;
  limit_amount?: string;
  deductible_amount?: string;
  premium_amount?: string;
  is_enabled?: boolean;
}

export interface PolicyDocumentRequirementRecord {
  id: number;
  policy: { id: number; policy_number: string | null };
  requirement_code: string;
  required: boolean;
  status: PolicyDocumentRequirementStatus;
  document_id: string;
  created_at: string;
  updated_at: string;
}

export interface CreatePolicyDocumentRequirementPayload {
  policy_id: number;
  requirement_code: string;
  required?: boolean;
  status?: PolicyDocumentRequirementStatus;
  document_id?: string;
}

export interface EndorsementRecord {
  id: number;
  policy: { id: number; policy_number: string | null };
  endorsement_number: string | null;
  type: EndorsementType;
  status: EndorsementStatus;
  effective_date: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateEndorsementPayload {
  policy_id: number;
  endorsement_number?: string | null;
  type: EndorsementType;
  status?: EndorsementStatus;
  effective_date: string;
  payload?: Record<string, unknown>;
}
