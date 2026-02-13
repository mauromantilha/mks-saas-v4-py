import { Injectable, inject } from "@angular/core";
import {
  ActivatedRouteSnapshot,
  CanActivate,
  CanActivateFn,
  Router,
  RouterStateSnapshot,
} from "@angular/router";
import { catchError, map, of } from "rxjs";

import { PermissionCode, PermissionService } from "./permission.service";
import { ToastService } from "../ui/toast.service";

@Injectable({ providedIn: "root" })
export class PermissionGuard implements CanActivate {
  constructor(
    private readonly permissionService: PermissionService,
    private readonly toast: ToastService,
    private readonly router: Router
  ) {}

  canActivate(route: ActivatedRouteSnapshot, _state: RouterStateSnapshot) {
    const singlePermission = route.data?.["permission"] as PermissionCode | undefined;
    const anyPermissions = route.data?.["anyPermissions"] as PermissionCode[] | undefined;

    return this.permissionService.loadPermissions().pipe(
      map(() => {
        let allowed = true;
        if (singlePermission) {
          allowed = this.permissionService.can(singlePermission);
        }
        if (allowed && anyPermissions && anyPermissions.length > 0) {
          allowed = this.permissionService.hasAnyPermission(anyPermissions);
        }
        if (allowed) {
          return true;
        }

        const errorMessage = this.permissionService.lastError();
        if (errorMessage) {
          this.toast.error(errorMessage);
        } else {
          this.toast.warning("Você não tem permissão para acessar esta área.");
        }
        return this.router.createUrlTree(["/login"]);
      }),
      catchError(() => {
        this.toast.error(
          this.permissionService.lastError()
            ?? "Não foi possível validar permissões. Acesso negado."
        );
        return of(this.router.createUrlTree(["/login"]));
      })
    );
  }
};

export const permissionGuard: CanActivateFn = (route, state) =>
  inject(PermissionGuard).canActivate(route, state);
