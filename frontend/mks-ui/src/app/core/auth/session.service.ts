import { computed, Injectable, signal } from "@angular/core";

import { TenantUserRole } from "../api/auth.types";
import { UserSession } from "./session.types";

const SESSION_STORAGE_KEY = "mks_ui_session_v1";

@Injectable({ providedIn: "root" })
export class SessionService {
  private readonly state = signal<UserSession | null>(this.readSession());

  readonly session = computed(() => this.state());
  readonly isAuthenticated = computed(() => {
    const current = this.state();
    return Boolean(current?.token);
  });

  saveSession(session: UserSession): void {
    this.state.set(session);
    this.writeSession(session);
  }

  clearSession(): void {
    this.state.set(null);
    try {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // Ignore storage errors in restricted environments.
    }
  }

  updateRole(role: TenantUserRole): void {
    const current = this.state();
    if (!current) {
      return;
    }

    const updated: UserSession = { ...current, role };
    this.state.set(updated);
    this.writeSession(updated);
  }

  private readSession(): UserSession | null {
    try {
      const raw = localStorage.getItem(SESSION_STORAGE_KEY);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw) as Partial<UserSession>;
      if (!parsed.token || !parsed.username) {
        return null;
      }
      return {
        token: parsed.token,
        tenantCode: parsed.tenantCode ?? null,
        username: parsed.username,
        role: parsed.role ?? null,
        platformAdmin: Boolean(parsed.platformAdmin),
        portalType: parsed.portalType === "CONTROL_PLANE" ? "CONTROL_PLANE" : "TENANT",
      };
    } catch {
      return null;
    }
  }

  private writeSession(session: UserSession): void {
    try {
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
    } catch {
      // Ignore storage errors in restricted environments.
    }
  }
}
