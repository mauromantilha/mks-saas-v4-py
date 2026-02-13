import { computed, Injectable, signal } from "@angular/core";
import { Observable, of } from "rxjs";
import { map } from "rxjs/operators";

import { CapabilitiesService } from "./capabilities.service";
import { resolvePermissionAliases } from "./permission-aliases";

export type PermissionCode = string;

@Injectable({ providedIn: "root" })
export class PermissionService {
  private readonly permissionsState = signal<Set<string>>(new Set<string>());
  private readonly loadedState = signal(false);
  private readonly lastErrorState = signal<string | null>(null);
  private readonly contextKeyState = signal<string | null>(null);
  private readonly versionState = signal(0);

  readonly loaded = computed(() => this.loadedState());
  readonly permissions = computed(() => Array.from(this.permissionsState()));
  readonly lastError = computed(() => this.lastErrorState());
  readonly version = computed(() => this.versionState());

  constructor(
    private readonly capabilitiesService: CapabilitiesService
  ) {}

  loadPermissions(force = false): Observable<string[]> {
    const contextKey = this.capabilitiesService.getCurrentContextKey();
    if (this.contextKeyState() !== contextKey) {
      this.resetState();
      this.contextKeyState.set(contextKey);
    }

    if (this.loadedState() && !force) {
      return of(this.permissions());
    }

    return this.capabilitiesService.loadCapabilities(force).pipe(
      map((snapshot) => {
        this.permissionsState.set(new Set<string>(snapshot.permissions));
        this.loadedState.set(true);
        this.contextKeyState.set(snapshot.contextKey);
        this.lastErrorState.set(snapshot.failed ? snapshot.errorMessage ?? "Falha ao carregar permissões." : null);
        this.bumpVersion();
        return Array.from(this.permissionsState());
      })
    );
  }

  clearPermissions(): void {
    this.capabilitiesService.clearCurrentSessionCache();
    this.resetState();
  }

  can(permission: PermissionCode): boolean {
    if (!permission) {
      return false;
    }
    const aliases = resolvePermissionAliases(permission);
    if (aliases.length === 0) {
      return false;
    }

    const currentPermissions = this.permissionsState();
    return aliases.some((candidate) => currentPermissions.has(candidate));
  }

  hasPermission(permission: PermissionCode): boolean {
    return this.can(permission);
  }

  hasAnyPermission(permissions: PermissionCode[]): boolean {
    return permissions.some((permission) => this.can(permission));
  }

  private resetState(): void {
    this.permissionsState.set(new Set<string>());
    this.loadedState.set(false);
    this.lastErrorState.set(null);
    this.contextKeyState.set(null);
    this.bumpVersion();
  }

  private bumpVersion(): void {
    this.versionState.update((value) => value + 1);
  }
}
