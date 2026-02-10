export type ReceivableInvoiceStatus = "OPEN" | "PAID" | "CANCELLED";
export type ReceivableInstallmentStatus = "OPEN" | "PAID" | "CANCELLED";
export type PayableStatus = "OPEN" | "PAID" | "CANCELLED";

export interface PayableRecord {
  id: number;
  recipient: number | null;
  recipient_name: string;
  beneficiary_name: string;
  amount: string;
  due_date: string;
  description: string;
  status: PayableStatus;
  source_ref: string;
  is_overdue: boolean;
  days_overdue: number;
  created_at: string;
  updated_at: string;
}

export interface ReceivableInstallmentRecord {
  id: number;
  invoice_id: number;
  invoice_status: ReceivableInvoiceStatus;
  policy_id: number | null;
  policy_number: string | null;
  insurer_id: number | null;
  insurer_name: string;
  payer_id: number;
  payer_name: string;
  number: number;
  amount: string;
  due_date: string;
  status: ReceivableInstallmentStatus;
  is_overdue: boolean;
  days_overdue: number;
  created_at: string;
  updated_at: string;
}

export interface ReceivableInvoiceRecord {
  id: number;
  payer: number;
  payer_name: string;
  policy: number | null;
  policy_number: string | null;
  total_amount: string;
  status: ReceivableInvoiceStatus;
  issue_date: string;
  description: string;
  installments: ReceivableInstallmentRecord[];
  created_at: string;
  updated_at: string;
}

export interface PolicyFinanceSummaryRecord {
  policy_id: number;
  policy_number: string | null;
  insurer_id: number;
  insurer_name: string;
  open_installments: number;
  paid_installments: number;
  cancelled_installments: number;
  overdue_installments: number;
  open_amount: string;
  paid_amount: string;
  cancelled_amount: string;
  overdue_amount: string;
}
