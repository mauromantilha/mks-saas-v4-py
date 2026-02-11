import { HttpParams } from "@angular/common/http";

export type QueryParamsValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | Array<string | number | boolean>;

export type QueryParamsMap = Record<string, QueryParamsValue>;

function isEmptyValue(value: QueryParamsValue): boolean {
  if (value === null || value === undefined) {
    return true;
  }
  if (typeof value === "string") {
    return value.trim().length === 0;
  }
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  return false;
}

function toQueryParamString(value: string | number | boolean): string {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return String(value);
}

export function buildHttpParams(params?: QueryParamsMap): HttpParams {
  let httpParams = new HttpParams();

  if (!params) {
    return httpParams;
  }

  for (const [key, rawValue] of Object.entries(params)) {
    if (isEmptyValue(rawValue)) {
      continue;
    }

    if (Array.isArray(rawValue)) {
      rawValue.forEach((item) => {
        httpParams = httpParams.append(key, toQueryParamString(item));
      });
      continue;
    }

    if (rawValue !== null && rawValue !== undefined) {
      httpParams = httpParams.set(key, toQueryParamString(rawValue));
    }
  }

  return httpParams;
}
