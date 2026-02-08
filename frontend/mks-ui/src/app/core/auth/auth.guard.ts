import { CanActivateFn, Router } from "@angular/router";
import { inject } from "@angular/core";

import { SessionService } from "./session.service";

export const authGuard: CanActivateFn = () => {
  const sessionService = inject(SessionService);
  const router = inject(Router);

  if (sessionService.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(["/login"]);
};
