import { HttpClient, HttpErrorResponse, HttpParams } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable, forkJoin, of, throwError } from "rxjs";
import { catchError, finalize, map, shareReplay } from "rxjs/operators";

import {
  AuthenticatedUserResponse,
  ResourceCapabilities,
  TenantCapabilitiesResponse,
  TenantUserRole,
} from "../api/auth.types";
import { AuthService } from "../api/auth.service";
import { API_CONFIG, buildApiUrl } from "../config/api-config";
import { SessionService } from "./session.service";
import { SessionPortalType, UserSession } from "./session.types";

const CAPABILITIES_TTL_MS = 5 * 60 * 1000;
const CAPABILITIES_STORAGE_KEY = "mks_ui_capabilities_cache_v1";

export interface CapabilitiesSnapshot {
  contextKey: string;
  portalType: SessionPortalType;
  tenantCode: string | null;
  username: string;
  permissions: string[];
  fetchedAt: number;
  expiresAt: number;
  source: "tenant-capabilities" | "control-panel-probe" | "cache" | "empty";
  failed: boolean;
  errorMessage?: string;
}

@Injectable({ providedIn: "root" })
export class CapabilitiesService {
  private readonly config = inject(API_CONFIG);
  private readonly controlPanelProbeUrl = buildApiUrl(
    this.config,
    "/api/control-panel/plans/"
  );
  private readonly memoryCache = new Map<string, CapabilitiesSnapshot>();
  private readonly inFlight = new Map<string, Observable<CapabilitiesSnapshot>>();

  constructor(
    private readonly authService: AuthService,
    private readonly sessionService: SessionService,
    private readonly http: HttpClient
  ) {
    this.restoreStorageCache();
  }

  getCurrentContextKey(): string | null {
    const session = this.sessionService.session();
    if (!session || !session.token) {
      return null;
    }
    return this.buildContextKey(session);
  }

  loadCapabilities(force = false): Observable<CapabilitiesSnapshot> {
    const session = this.sessionService.session();
    if (!session || !session.token) {
      return of(this.buildEmptySnapshot("anonymous"));
    }

    const contextKey = this.buildContextKey(session);
    if (!force) {
      const cached = this.memoryCache.get(contextKey);
      if (cached && this.isFresh(cached)) {
        return of({ ...cached, source: "cache" });
      }
    }

    const inFlightRequest = this.inFlight.get(contextKey);
    if (inFlightRequest) {
      return inFlightRequest;
    }

    const request$ = this.fetchCapabilitiesSnapshot(session, contextKey).pipe(
      map((snapshot) => this.storeSnapshot(snapshot)),
      catchError((error: unknown) =>
        of(
          this.storeSnapshot(
            this.buildFailedSnapshot(
              session,
              contextKey,
              this.resolveLoadErrorMessage(error)
            )
          )
        )
      ),
      finalize(() => this.inFlight.delete(contextKey)),
      shareReplay({ bufferSize: 1, refCount: false })
    );

    this.inFlight.set(contextKey, request$);
    return request$;
  }

  clearCurrentSessionCache(): void {
    const contextKey = this.getCurrentContextKey();
    if (!contextKey) {
      return;
    }
    this.memoryCache.delete(contextKey);
    this.persistStorageCache();
  }

  private fetchCapabilitiesSnapshot(
    session: UserSession,
    contextKey: string
  ): Observable<CapabilitiesSnapshot> {
    if (session.portalType === "TENANT") {
      if (!session.tenantCode) {
        return of(
          this.buildFailedSnapshot(
            session,
            contextKey,
            "Tenant não identificado para carregar permissões."
          )
        );
      }

      return this.authService.getTenantCapabilities().pipe(
        map((response) =>
          this.buildTenantSnapshot(session, contextKey, response)
        )
      );
    }

    return this.resolveControlPanelSnapshot(session, contextKey);
  }

  private resolveControlPanelSnapshot(
    session: UserSession,
    contextKey: string
  ): Observable<CapabilitiesSnapshot> {
    return forkJoin({
      user: this.authService.getAuthenticatedUser(session.token),
      hasControlPanelAccess: this.http
        .get<unknown>(this.controlPanelProbeUrl, {
          params: new HttpParams().set("page", "1").set("page_size", "1"),
        })
        .pipe(
          map(() => true),
          catchError((error: unknown) => {
            if (
              error instanceof HttpErrorResponse &&
              [401, 403, 404].includes(error.status)
            ) {
              return of(false);
            }
            return throwError(() => error);
          })
        ),
    }).pipe(
      map(({ user, hasControlPanelAccess }) =>
        this.buildControlPanelSnapshot(
          session,
          contextKey,
          user,
          hasControlPanelAccess
        )
      )
    );
  }

  private buildTenantSnapshot(
    session: UserSession,
    contextKey: string,
    response: TenantCapabilitiesResponse
  ): CapabilitiesSnapshot {
    const now = Date.now();
    return {
      contextKey,
      portalType: session.portalType,
      tenantCode: response.tenant_code ?? session.tenantCode,
      username: session.username,
      permissions: this.resolveTenantPermissions(response),
      fetchedAt: now,
      expiresAt: now + CAPABILITIES_TTL_MS,
      source: "tenant-capabilities",
      failed: false,
    };
  }

  private buildControlPanelSnapshot(
    session: UserSession,
    contextKey: string,
    user: AuthenticatedUserResponse,
    hasControlPanelAccess: boolean
  ): CapabilitiesSnapshot {
    const now = Date.now();
    const permissions = hasControlPanelAccess
      ? this.resolveControlPanelPermissions(user)
      : [];
    return {
      contextKey,
      portalType: session.portalType,
      tenantCode: session.tenantCode,
      username: session.username,
      permissions,
      fetchedAt: now,
      expiresAt: now + CAPABILITIES_TTL_MS,
      source: "control-panel-probe",
      failed: false,
    };
  }

  private buildFailedSnapshot(
    session: UserSession,
    contextKey: string,
    errorMessage: string
  ): CapabilitiesSnapshot {
    const now = Date.now();
    return {
      contextKey,
      portalType: session.portalType,
      tenantCode: session.tenantCode,
      username: session.username,
      permissions: [],
      fetchedAt: now,
      expiresAt: now + CAPABILITIES_TTL_MS,
      source: "empty",
      failed: true,
      errorMessage,
    };
  }

  private buildEmptySnapshot(username: string): CapabilitiesSnapshot {
    const now = Date.now();
    return {
      contextKey: "anonymous",
      portalType: "TENANT",
      tenantCode: null,
      username,
      permissions: [],
      fetchedAt: now,
      expiresAt: now + CAPABILITIES_TTL_MS,
      source: "empty",
      failed: false,
    };
  }

  private resolveTenantPermissions(
    response: TenantCapabilitiesResponse
  ): string[] {
    const permissions = new Set<string>(["tenant.access"]);
    this.addRolePermissions(response.role, permissions);

    const capabilities = response.capabilities ?? {};
    for (const [resource, actions] of Object.entries(capabilities)) {
      this.addResourcePermissions(resource, actions, permissions);
    }

    return Array.from(permissions);
  }

  private addRolePermissions(
    role: TenantUserRole,
    permissions: Set<string>
  ): void {
    if (!role) {
      return;
    }

    const normalizedRole = String(role).toUpperCase();
    if (normalizedRole === "OWNER") {
      permissions.add("tenant.role.owner");
      permissions.add("tenant.role.manager");
      permissions.add("tenant.role.member");
      permissions.add("tenant.rbac.manage");
      return;
    }
    if (normalizedRole === "MANAGER") {
      permissions.add("tenant.role.manager");
      permissions.add("tenant.role.member");
      return;
    }
    if (normalizedRole === "MEMBER") {
      permissions.add("tenant.role.member");
    }
  }

  private addResourcePermissions(
    resource: string,
    actions: ResourceCapabilities,
    permissions: Set<string>
  ): void {
    if (!actions) {
      return;
    }

    const add = (action: keyof ResourceCapabilities): void => {
      if (actions[action]) {
        permissions.add(`${resource}.${action}`);
      }
    };

    add("list");
    add("retrieve");
    add("create");
    add("update");
    add("partial_update");
    add("delete");

    if (actions.list || actions.retrieve) {
      permissions.add(`${resource}.read`);
    }
    if (actions.create || actions.update || actions.partial_update || actions.delete) {
      permissions.add(`${resource}.write`);
    }
  }

  private resolveControlPanelPermissions(
    user: AuthenticatedUserResponse
  ): string[] {
    const permissions = new Set<string>([
      "cp.access",
      "cp.dashboard.view",
      "cp.tenants.view",
      "cp.tenants.manage",
      "cp.tenants.notes.manage",
      "cp.tenants.delete",
      "cp.plans.view",
      "cp.plans.manage",
      "cp.contracts.view",
      "cp.monitoring.view",
      "cp.monitoring.manage",
      "cp.audit.view",
    ]);

    if (user.is_superuser) {
      permissions.add("cp.superadmin");
    }

    return Array.from(permissions);
  }

  private resolveLoadErrorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 401 || error.status === 403) {
        return "Permissões não autorizadas para este usuário.";
      }
      return "Falha ao carregar permissões do backend.";
    }
    return "Falha inesperada ao validar permissões.";
  }

  private storeSnapshot(snapshot: CapabilitiesSnapshot): CapabilitiesSnapshot {
    this.memoryCache.set(snapshot.contextKey, snapshot);
    this.persistStorageCache();
    return snapshot;
  }

  private isFresh(snapshot: CapabilitiesSnapshot): boolean {
    return snapshot.expiresAt > Date.now();
  }

  private restoreStorageCache(): void {
    try {
      const raw = localStorage.getItem(CAPABILITIES_STORAGE_KEY);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as Record<string, CapabilitiesSnapshot>;
      const now = Date.now();
      for (const [key, snapshot] of Object.entries(parsed)) {
        if (!snapshot || snapshot.expiresAt <= now) {
          continue;
        }
        this.memoryCache.set(key, snapshot);
      }
    } catch {
      // Ignore localStorage parse errors.
    }
  }

  private persistStorageCache(): void {
    try {
      const now = Date.now();
      const payload: Record<string, CapabilitiesSnapshot> = {};
      for (const [key, snapshot] of this.memoryCache.entries()) {
        if (snapshot.expiresAt <= now) {
          continue;
        }
        payload[key] = snapshot;
      }
      localStorage.setItem(CAPABILITIES_STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // Ignore localStorage write errors.
    }
  }

  private buildContextKey(session: UserSession): string {
    const tenantCode = session.tenantCode ?? "-";
    const portal = session.portalType.toLowerCase();
    return `${portal}:${session.username}:${tenantCode}`;
  }
}
