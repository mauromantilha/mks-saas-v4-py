import { Injectable } from "@angular/core";

import { SessionService } from "./session.service";

export type PermissionCode =
  | "control_panel.access"
  | "control_panel.dashboard"
  | "control_panel.tenants.read"
  | "control_panel.plans.read"
  | "control_panel.contracts.read"
  | "control_panel.monitoring.read"
  | "control_panel.audit.read"
  | "control_panel.superadmin";

@Injectable({ providedIn: "root" })
export class PermissionService {
  constructor(private readonly sessionService: SessionService) {}

  hasPermission(permission: PermissionCode): boolean {
    const session = this.sessionService.session();
    if (!session || !session.token) {
      return false;
    }

    if (!session.platformAdmin || session.portalType !== "CONTROL_PLANE") {
      return false;
    }

    if (permission === "control_panel.superadmin") {
      return session.isSuperuser === true;
    }

    return true;
  }

  hasAnyPermission(permissions: PermissionCode[]): boolean {
    return permissions.some((permission) => this.hasPermission(permission));
  }
}
