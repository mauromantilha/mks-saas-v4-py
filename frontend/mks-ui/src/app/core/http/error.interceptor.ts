import { HttpErrorResponse, HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";
import { Router } from "@angular/router";
import { catchError, throwError } from "rxjs";

import { SessionService } from "../auth/session.service";
import { ToastService } from "../ui/toast.service";
import { normalizeApiError } from "./api-error.util";

function isAuthTokenEndpoint(url: string): boolean {
  return url.endsWith("/api/auth/token/") || url.endsWith("/api/auth/token");
}

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const sessionService = inject(SessionService);
  const toastService = inject(ToastService);

  return next(req).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse)) {
        return throwError(() => error);
      }

      const normalized = normalizeApiError(error);

      if (error.status === 401 && !isAuthTokenEndpoint(req.url)) {
        sessionService.clearSession();
        toastService.warning("Sessão expirada. Faça login novamente.");
        void router.navigate(["/login"]);
      } else if (error.status === 403) {
        toastService.warning("Você não tem permissão para executar esta ação.");
      } else if (error.status === 400 || error.status === 422) {
        toastService.error(normalized.message);
      }

      const enrichedError = Object.assign(error, { normalizedError: normalized });
      return throwError(() => enrichedError);
    })
  );
};

