export type ReceivableInvoiceStatus = "OPEN" | "PAID" | "CANCELLED";
export type ReceivableInstallmentStatus = "OPEN" | "PAID" | "CANCELLED";

export interface ReceivableInstallmentRecord {
  id: number;
  number: number;
  amount: string;
  due_date: string;
  status: ReceivableInstallmentStatus;
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
