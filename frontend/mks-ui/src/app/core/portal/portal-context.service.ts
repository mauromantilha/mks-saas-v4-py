import { Injectable } from "@angular/core";

import { environment } from "../../../environments/environment";

type PortalType = "CONTROL_PLANE" | "TENANT";

@Injectable({ providedIn: "root" })
export class PortalContextService {
  private readonly hostnameValue = this.readHostname();
  private readonly controlPlaneSubdomain = environment.controlPlaneSubdomain.toLowerCase();
  private readonly tenantBaseDomain = environment.tenantBaseDomain.toLowerCase();
  private readonly reservedSubdomains = new Set(
    [
      this.controlPlaneSubdomain,
      "www",
      "api",
      "admin",
      "static",
      "media",
      "localhost",
    ].map((item) => item.toLowerCase())
  );

  hostname(): string {
    return this.hostnameValue;
  }

  portalType(): PortalType {
    if (this.isControlPlanePortal()) {
      return "CONTROL_PLANE";
    }
    return "TENANT";
  }

  isControlPlanePortal(): boolean {
    const hostname = this.hostnameValue;
    if (!hostname) {
      return false;
    }
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return false;
    }
    if (hostname === this.controlPlaneSubdomain) {
      return true;
    }
    return hostname.startsWith(`${this.controlPlaneSubdomain}.`);
  }

  suggestedTenantCode(): string {
    const hostname = this.hostnameValue;
    if (!hostname || this.isControlPlanePortal()) {
      return "";
    }
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return "";
    }

    if (
      this.tenantBaseDomain &&
      hostname.endsWith(`.${this.tenantBaseDomain}`)
    ) {
      const subdomain = hostname.slice(0, -(`.${this.tenantBaseDomain}`.length));
      if (subdomain && !subdomain.includes(".") && !this.reservedSubdomains.has(subdomain)) {
        return subdomain;
      }
      return "";
    }

    if (hostname.endsWith(".localhost")) {
      const localSubdomain = hostname.split(".", 1)[0].toLowerCase();
      if (localSubdomain && !this.reservedSubdomains.has(localSubdomain)) {
        return localSubdomain;
      }
      return "";
    }

    const parts = hostname.split(".");
    if (parts.length >= 3) {
      const candidate = parts[0].toLowerCase();
      if (!this.reservedSubdomains.has(candidate)) {
        return candidate;
      }
    }
    return "";
  }

  private readHostname(): string {
    if (typeof window === "undefined" || !window.location?.hostname) {
      return "";
    }
    return window.location.hostname.toLowerCase();
  }
}
