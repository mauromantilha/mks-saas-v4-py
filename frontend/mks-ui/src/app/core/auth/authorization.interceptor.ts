import { HttpInterceptorFn } from "@angular/common/http";

import { authTenantInterceptor } from "./auth.interceptor";

export const authorizationInterceptor: HttpInterceptorFn = (req, next) =>
  authTenantInterceptor(req, next);

