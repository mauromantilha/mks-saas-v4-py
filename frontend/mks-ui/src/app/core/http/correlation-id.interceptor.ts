import { HttpInterceptorFn } from "@angular/common/http";

function generateCorrelationId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const random = Math.random().toString(36).slice(2);
  return `cid-${Date.now()}-${random}`;
}

export const correlationIdInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.headers.has("X-Correlation-ID")) {
    return next(req);
  }
  return next(req.clone({ setHeaders: { "X-Correlation-ID": generateCorrelationId() } }));
};

