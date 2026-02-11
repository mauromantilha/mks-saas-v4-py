import { HttpErrorResponse } from "@angular/common/http";

export interface ApiErrorNormalized {
  status: number;
  message: string;
  validation: Record<string, string[]>;
}

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }
  if (value === null || value === undefined) {
    return [];
  }
  return [String(value)];
}

export function normalizeApiError(error: HttpErrorResponse): ApiErrorNormalized {
  const payload = (error.error ?? {}) as Record<string, unknown>;
  const validation: Record<string, string[]> = {};

  if (payload && typeof payload === "object") {
    for (const [key, value] of Object.entries(payload)) {
      if (["detail", "message", "non_field_errors"].includes(key)) {
        continue;
      }
      validation[key] = toStringArray(value);
    }
  }

  const detail = payload?.["detail"];
  const message = payload?.["message"];
  const nonFieldErrors = payload?.["non_field_errors"];
  const fallbackMessage =
    toStringArray(detail)[0] ||
    toStringArray(message)[0] ||
    toStringArray(nonFieldErrors)[0] ||
    error.message ||
    "Erro inesperado na API.";

  return {
    status: error.status,
    message: fallbackMessage,
    validation,
  };
}

