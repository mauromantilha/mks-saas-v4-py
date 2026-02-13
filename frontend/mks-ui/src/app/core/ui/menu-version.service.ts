import { Injectable, signal } from "@angular/core";
import { take } from "rxjs";

import { AuthService } from "../api/auth.service";
import { ResourceCapabilities } from "../api/auth.types";
import { SessionPortalType, UserSession } from "../auth/session.types";
import { environment } from "../../../environments/environment";

const MENU_V2_STORAGE_KEY = "mks_ui_menu_v2";
const MENU_V2_QUERY_PARAM = "menu_v2";
const MENU_V2_CAPABILITY_KEYS = ["menu_v2", "ui.menu_v2", "ui_menu_v2"];

@Injectable({ providedIn: "root" })
export class MenuVersionService {
  private readonly menuV2EnabledState = signal(this.resolveDefaultValue());
  private readonly resolvedTenantCodeState = signal<string | null>(null);
  private readonly inFlightTenantCodeState = signal<string | null>(null);

  constructor(private readonly authService: AuthService) {}

  isMenuV2Enabled(): boolean {
    return this.menuV2EnabledState();
  }

  resolveForTenant(session: UserSession | null, portalType: SessionPortalType): void {
    if (!session || portalType !== "TENANT" || !session.tenantCode) {
      return;
    }

    const tenantCode = session.tenantCode;
    const override = this.readTenantOverride(tenantCode);
    if (override !== null) {
      this.menuV2EnabledState.set(override);
      this.resolvedTenantCodeState.set(tenantCode);
      return;
    }

    if (
      this.resolvedTenantCodeState() === tenantCode ||
      this.inFlightTenantCodeState() === tenantCode
    ) {
      return;
    }

    this.inFlightTenantCodeState.set(tenantCode);
    this.authService
      .getTenantCapabilities()
      .pipe(take(1))
      .subscribe({
        next: (response) => {
          const resolved = this.resolveFromCapabilities(response.capabilities);
          if (resolved !== null) {
            this.menuV2EnabledState.set(resolved);
          }
          this.resolvedTenantCodeState.set(tenantCode);
          this.inFlightTenantCodeState.set(null);
        },
        error: () => {
          this.resolvedTenantCodeState.set(tenantCode);
          this.inFlightTenantCodeState.set(null);
        },
      });
  }

  private resolveFromCapabilities(
    capabilities: Record<string, ResourceCapabilities>
  ): boolean | null {
    for (const key of MENU_V2_CAPABILITY_KEYS) {
      const capability = capabilities[key];
      if (capability) {
        return capability.list;
      }
    }
    return null;
  }

  private resolveDefaultValue(): boolean {
    const queryValue = this.readQueryParamOverride();
    if (queryValue !== null) {
      return queryValue;
    }

    const globalOverride = this.readGlobalOverride();
    if (globalOverride !== null) {
      return globalOverride;
    }

    const stored = this.readStorageBoolean(MENU_V2_STORAGE_KEY);
    if (stored !== null) {
      return stored;
    }

    return environment.menuV2Enabled;
  }

  private readTenantOverride(tenantCode: string): boolean | null {
    const tenantKey = `${MENU_V2_STORAGE_KEY}:${tenantCode}`;
    return this.readStorageBoolean(tenantKey);
  }

  private readGlobalOverride(): boolean | null {
    const win = globalThis as typeof globalThis & {
      __MKS_MENU_V2__?: boolean;
    };
    return typeof win.__MKS_MENU_V2__ === "boolean" ? win.__MKS_MENU_V2__ : null;
  }

  private readQueryParamOverride(): boolean | null {
    try {
      const params = new URLSearchParams(globalThis.location?.search ?? "");
      return this.parseBooleanValue(params.get(MENU_V2_QUERY_PARAM));
    } catch {
      return null;
    }
  }

  private readStorageBoolean(key: string): boolean | null {
    try {
      return this.parseBooleanValue(localStorage.getItem(key));
    } catch {
      return null;
    }
  }

  private parseBooleanValue(value: string | null | undefined): boolean | null {
    if (value === "1" || value === "true") {
      return true;
    }
    if (value === "0" || value === "false") {
      return false;
    }
    return null;
  }
}
