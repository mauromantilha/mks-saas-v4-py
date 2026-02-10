import { CanActivateFn, Router } from "@angular/router";
import { inject } from "@angular/core";

import { PermissionCode, PermissionService } from "./permission.service";

export const permissionGuard: CanActivateFn = (route) => {
  const permissionService = inject(PermissionService);
  const router = inject(Router);

  const singlePermission = route.data?.["permission"] as PermissionCode | undefined;
  const anyPermissions = route.data?.["anyPermissions"] as PermissionCode[] | undefined;

  let allowed = true;
  if (singlePermission) {
    allowed = permissionService.hasPermission(singlePermission);
  }
  if (allowed && anyPermissions && anyPermissions.length > 0) {
    allowed = permissionService.hasAnyPermission(anyPermissions);
  }

  if (allowed) {
    return true;
  }
  return router.createUrlTree(["/login"]);
};
