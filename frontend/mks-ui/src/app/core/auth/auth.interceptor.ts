import { HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";

import { AuthService } from "../api/auth.service";
import { API_CONFIG } from "../config/api-config";
import { SessionService } from "./session.service";

function isTokenEndpoint(url: string): boolean {
  return url.endsWith("/api/auth/token/") || url.endsWith("/api/auth/token");
}

function isApiRequest(url: string): boolean {
  return url.includes("/api/");
}

function isTenantScopedApiRequest(url: string): boolean {
  return (
    url.includes("/api/") &&
    !url.includes("/platform/api/") &&
    !url.includes("/api/control-panel/")
  );
}

export const authTenantInterceptor: HttpInterceptorFn = (req, next) => {
  const config = inject(API_CONFIG);
  const authService = inject(AuthService);
  const sessionService = inject(SessionService);
  const session = sessionService.session();
  const tenantCode = session?.tenantCode ?? null;
  const accessToken = authService.getAccessToken() ?? session?.token ?? null;

  if (!isApiRequest(req.url) || isTokenEndpoint(req.url) || !accessToken) {
    return next(req);
  }

  let headers = req.headers;

  if (!headers.has("Authorization")) {
    headers = headers.set("Authorization", `${config.authHeaderScheme} ${accessToken}`);
  }
  if (
    isTenantScopedApiRequest(req.url) &&
    tenantCode &&
    !headers.has(config.tenantIdHeader)
  ) {
    headers = headers.set(config.tenantIdHeader, tenantCode);
  }

  return next(req.clone({ headers }));
};
