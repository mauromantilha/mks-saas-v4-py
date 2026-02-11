import { computed, Injectable, signal } from "@angular/core";
import { Observable, of } from "rxjs";

import { SessionService } from "./session.service";

export type PermissionCode = string;

@Injectable({ providedIn: "root" })
export class PermissionService {
  private readonly permissionsState = signal<Set<string>>(new Set<string>());
  private readonly loadedState = signal(false);

  readonly loaded = computed(() => this.loadedState());
  readonly permissions = computed(() => Array.from(this.permissionsState()));

  constructor(private readonly sessionService: SessionService) {}

  loadPermissions(force = false): Observable<string[]> {
    if (this.loadedState() && !force) {
      return of(this.permissions());
    }

    const mockPermissions = this.resolveMockPermissions();
    this.permissionsState.set(mockPermissions);
    this.loadedState.set(true);
    return of(Array.from(mockPermissions));
  }

  clearPermissions(): void {
    this.permissionsState.set(new Set<string>());
    this.loadedState.set(false);
  }

  can(permission: PermissionCode): boolean {
    if (!this.loadedState()) {
      this.loadPermissions();
    }

    const resolved = this.resolvePermissionAlias(permission);
    return this.permissionsState().has(resolved);
  }

  hasPermission(permission: PermissionCode): boolean {
    return this.can(permission);
  }

  hasAnyPermission(permissions: PermissionCode[]): boolean {
    return permissions.some((permission) => this.can(permission));
  }

  private resolveMockPermissions(): Set<string> {
    const session = this.sessionService.session();
    if (!session || !session.token) {
      return new Set<string>();
    }

    // Portal host is already enforced by portalGuard. Keep permissions resilient
    // even if a stale session has an old portalType value.
    if (!session.platformAdmin) {
      return new Set<string>();
    }

    const basePermissions = new Set<string>([
      "cp.access",
      "cp.dashboard.view",
      "cp.tenants.view",
      "cp.tenants.manage",
      "cp.tenants.notes.manage",
      "cp.plans.view",
      "cp.contracts.view",
      "cp.monitoring.view",
      "cp.audit.view",
    ]);

    if (session.isSuperuser === true) {
      basePermissions.add("cp.superadmin");
      basePermissions.add("cp.tenants.delete");
      basePermissions.add("cp.plans.manage");
    }

    return basePermissions;
  }

  private resolvePermissionAlias(permission: string): string {
    const aliases: Record<string, string> = {
      "control_panel.access": "cp.access",
      "control_panel.dashboard": "cp.dashboard.view",
      "control_panel.tenants.read": "cp.tenants.view",
      "control_panel.tenants.notes.manage": "cp.tenants.notes.manage",
      "control_panel.plans.read": "cp.plans.view",
      "control_panel.plans.manage": "cp.plans.manage",
      "control_panel.contracts.read": "cp.contracts.view",
      "control_panel.monitoring.read": "cp.monitoring.view",
      "control_panel.audit.read": "cp.audit.view",
      "control_panel.superadmin": "cp.superadmin",
    };
    return aliases[permission] ?? permission;
  }
}
