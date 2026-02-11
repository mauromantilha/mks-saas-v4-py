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

@Injectable({ providedIn: "root" })
export class PermissionGuard implements CanActivate {
  constructor(
    private readonly permissionService: PermissionService,
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
        return allowed ? true : this.router.createUrlTree(["/login"]);
      }),
      catchError(() => of(this.router.createUrlTree(["/login"])))
    );
  }
};

export const permissionGuard: CanActivateFn = (route, state) =>
  inject(PermissionGuard).canActivate(route, state);
