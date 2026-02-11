import { InjectionToken, Provider } from "@angular/core";

export type AuthHeaderScheme = "Bearer" | "Token";

export interface ApiConfig {
  baseUrl: string;
  tenantIdHeader: string;
  authHeaderScheme: AuthHeaderScheme;
}

export const API_CONFIG = new InjectionToken<ApiConfig>("API_CONFIG");

export function provideApiConfig(config: ApiConfig): Provider {
  return {
    provide: API_CONFIG,
    useValue: config,
  };
}

export function buildApiUrl(config: ApiConfig, path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!config.baseUrl) {
    return normalizedPath;
  }
  return `${config.baseUrl.replace(/\/$/, "")}${normalizedPath}`;
}

