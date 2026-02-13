export type PermissionAliasMap = Record<string, string[]>;

// Canonical permission names used by routes/components mapped to concrete
// capability strings exposed by the backend.
export const PERMISSION_ALIAS_MAP: PermissionAliasMap = {
  // Control Panel aliases.
  "control_panel.access": ["cp.access"],
  "control_panel.dashboard": ["cp.dashboard.view"],
  "control_panel.tenants.read": ["cp.tenants.view"],
  "control_panel.tenants.notes.manage": ["cp.tenants.notes.manage"],
  "control_panel.plans.read": ["cp.plans.view"],
  "control_panel.plans.manage": ["cp.plans.manage"],
  "control_panel.contracts.read": ["cp.contracts.view"],
  "control_panel.monitoring.read": ["cp.monitoring.view"],
  "control_panel.audit.read": ["cp.audit.view"],
  "control_panel.superadmin": ["cp.superadmin"],

  // Tenant canonical permissions (menu/routes).
  "tenant.dashboard.view": ["dashboard.list"],
  "tenant.customers.view": ["customers.list"],
  "tenant.leads.view": ["leads.list"],
  "tenant.opportunities.view": ["opportunities.list"],
  "tenant.activities.view": ["activities.list"],
  "tenant.ai_assistant.view": ["ai_assistant.list", "ai_assistant.create"],
  "tenant.proposal_options.view": ["proposal_options.list"],
  "tenant.policy_requests.view": ["policy_requests.list"],
  "tenant.insurers.view": ["insurers.list"],
  "tenant.apolices.view": ["apolices.list", "policies.list"],
  "tenant.fiscal.view": ["invoices.list"],
  "tenant.finance.view": [
    "invoices.list",
    "installments.list",
    "payables.list",
    "commission_accruals.list",
    "commission_payouts.list",
  ],
  "tenant.commissions.view": ["commission_accruals.list", "commission_payouts.list"],
  "tenant.installments.view": ["installments.list"],
  "tenant.payables.view": ["payables.list"],
  "tenant.ledger.view": ["ledger.list"],
  "tenant.members.view": ["tenant.role.member"],
  "tenant.members.manage": ["tenant.role.owner"],
  "tenant.rbac.manage": ["tenant.role.owner"],
  "tenant.admin.view": ["tenant.role.manager", "tenant.role.owner"],
};

export function resolvePermissionAliases(permission: string): string[] {
  if (!permission) {
    return [];
  }

  const visited = new Set<string>();
  const resolved = new Set<string>();

  const expand = (candidate: string): void => {
    if (!candidate || visited.has(candidate)) {
      return;
    }
    visited.add(candidate);

    const mapped = PERMISSION_ALIAS_MAP[candidate];
    if (!mapped || mapped.length === 0) {
      resolved.add(candidate);
      return;
    }

    for (const alias of mapped) {
      if (PERMISSION_ALIAS_MAP[alias]) {
        expand(alias);
      } else {
        resolved.add(alias);
      }
    }
  };

  expand(permission);
  return Array.from(resolved);
}
