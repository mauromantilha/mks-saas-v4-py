import { HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";

import { environment } from "../../../environments/environment";
import { SessionService } from "./session.service";

function isTokenEndpoint(url: string): boolean {
  return url.endsWith("/api/auth/token/") || url.endsWith("/api/auth/token");
}

function isApiRequest(url: string): boolean {
  return url.includes("/api/");
}

export const authTenantInterceptor: HttpInterceptorFn = (req, next) => {
  const sessionService = inject(SessionService);
  const session = sessionService.session();

  if (!isApiRequest(req.url) || isTokenEndpoint(req.url) || !session) {
    return next(req);
  }

  let headers = req.headers;

  if (!headers.has("Authorization")) {
    headers = headers.set("Authorization", `Token ${session.token}`);
  }
  if (!headers.has(environment.tenantIdHeader)) {
    headers = headers.set(environment.tenantIdHeader, session.tenantCode);
  }

  return next(req.clone({ headers }));
};
