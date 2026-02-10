import { CanActivateFn, Router } from "@angular/router";
import { inject } from "@angular/core";

import { SessionService } from "../auth/session.service";
import { PortalContextService } from "./portal-context.service";

type PortalType = "CONTROL_PLANE" | "TENANT";

export const portalGuard: CanActivateFn = (route) => {
  const sessionService = inject(SessionService);
  const portalContextService = inject(PortalContextService);
  const router = inject(Router);

  const requiredPortal = (route.data?.["portal"] ?? "") as PortalType | "";
  if (!requiredPortal) {
    return true;
  }

  const hostPortal = portalContextService.portalType();
  const session = sessionService.session();

  if (hostPortal !== requiredPortal) {
    // Hard separation: platform routes only on sistema.*, tenant routes only on tenant hosts.
    if (hostPortal === "CONTROL_PLANE") {
      return router.createUrlTree([sessionService.isAuthenticated() ? "/control-panel/dashboard" : "/login"]);
    }
    return router.createUrlTree([sessionService.isAuthenticated() ? "/tenant/dashboard" : "/login"]);
  }

  if (!sessionService.isAuthenticated()) {
    return router.createUrlTree(["/login"]);
  }

  if (requiredPortal === "CONTROL_PLANE") {
    if (!session?.platformAdmin) {
      sessionService.clearSession();
      return router.createUrlTree(["/login"]);
    }
    return true;
  }

  if (!session?.tenantCode) {
    sessionService.clearSession();
    return router.createUrlTree(["/login"]);
  }

  return true;
};
