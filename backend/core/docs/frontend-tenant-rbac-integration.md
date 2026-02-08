# Frontend Integration: Tenant RBAC

This project now exposes tenant-level RBAC management via:

- `GET /api/auth/tenant-rbac/`
- `PUT /api/auth/tenant-rbac/`
- `PATCH /api/auth/tenant-rbac/`

And tenant membership management via:

- `GET /api/auth/tenant-members/`
- `POST /api/auth/tenant-members/`
- `PATCH /api/auth/tenant-members/{membership_id}/`
- `DELETE /api/auth/tenant-members/{membership_id}/`

Headers required on all calls:

- `Authorization: Token <token>`
- `X-Tenant-ID: <tenant_code>`

## Behavior

- `GET`: any authenticated active tenant member (`MEMBER`, `MANAGER`, `OWNER`).
- `PUT` and `PATCH`: only `OWNER`.
- Tenant members write operations (`POST`, `PATCH`, `DELETE`): only `OWNER`.
- Validation is strict:
  - unknown resources return `400`.
  - invalid method/role shape returns `400`.

## Response shape

```json
{
  "tenant_code": "acme",
  "rbac_overrides": {
    "apolices": {
      "POST": ["MANAGER", "OWNER"]
    }
  },
  "effective_role_matrices": {
    "customers": {
      "GET": ["MANAGER", "MEMBER", "OWNER"],
      "POST": ["MANAGER", "OWNER"],
      "PUT": ["MANAGER", "OWNER"],
      "PATCH": ["MANAGER", "OWNER"],
      "DELETE": ["OWNER"],
      "HEAD": ["MANAGER", "MEMBER", "OWNER"],
      "OPTIONS": ["MANAGER", "MEMBER", "OWNER"]
    }
  }
}
```

## Error examples

- Missing tenant:

```json
{"detail": "Tenant not provided. Send X-Tenant-ID or use tenant subdomain."}
```

- Non-owner write:

```json
{"detail":"Only OWNER users can manage tenant RBAC settings."}
```

- Invalid payload:

```json
{
  "detail": {
    "unknown_resource": [
      "Unknown resource 'unknown_resource'. Allowed: ['apolices', 'customers', 'endossos', 'leads', 'opportunities']"
    ]
  }
}
```

## Frontend Typescript contracts

```ts
export type TenantRole = "MEMBER" | "MANAGER" | "OWNER";
export type HttpMethod = "GET" | "HEAD" | "OPTIONS" | "POST" | "PUT" | "PATCH" | "DELETE";
export type ResourceKey = "customers" | "leads" | "opportunities" | "apolices" | "endossos";

export type TenantRbacOverrides = Partial<
  Record<ResourceKey, Partial<Record<HttpMethod, TenantRole[]>>>
>;

export type TenantRoleMatrix = Partial<Record<HttpMethod, TenantRole[]>>;

export interface TenantRbacResponse {
  tenant_code: string;
  rbac_overrides: TenantRbacOverrides;
  effective_role_matrices: Record<ResourceKey, TenantRoleMatrix>;
}
```

## Angular service (example)

```ts
import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

@Injectable({ providedIn: "root" })
export class TenantRbacService {
  private readonly baseUrl = "/api/auth/tenant-rbac/";

  constructor(private http: HttpClient) {}

  get(tenantCode: string, token: string): Observable<TenantRbacResponse> {
    return this.http.get<TenantRbacResponse>(this.baseUrl, {
      headers: this.headers(tenantCode, token),
    });
  }

  put(
    tenantCode: string,
    token: string,
    rbacOverrides: TenantRbacOverrides
  ): Observable<TenantRbacResponse> {
    return this.http.put<TenantRbacResponse>(
      this.baseUrl,
      { rbac_overrides: rbacOverrides },
      { headers: this.headers(tenantCode, token) }
    );
  }

  patch(
    tenantCode: string,
    token: string,
    rbacOverrides: TenantRbacOverrides
  ): Observable<TenantRbacResponse> {
    return this.http.patch<TenantRbacResponse>(
      this.baseUrl,
      { rbac_overrides: rbacOverrides },
      { headers: this.headers(tenantCode, token) }
    );
  }

  private headers(tenantCode: string, token: string): HttpHeaders {
    return new HttpHeaders({
      Authorization: `Token ${token}`,
      "X-Tenant-ID": tenantCode,
    });
  }
}
```

## Recommended screen behavior

1. Load `GET /api/auth/capabilities/` and `GET /api/auth/tenant-rbac/`.
2. If role is not `OWNER`, show read-only matrices.
3. If role is `OWNER`, allow edit of allowed roles per method/resource.
4. On save:
   - full replace: `PUT`
   - partial merge: `PATCH`
5. Render backend `detail` message on `400/403`.

## Validated local smoke tests (PostgreSQL + runserver)

- `GET /healthz/` -> `200`
- `GET /api/auth/tenant-rbac/` without tenant -> `400`
- `GET /api/auth/tenant-rbac/` as `MEMBER` -> `200`
- `PUT /api/auth/tenant-rbac/` as `MEMBER` -> `403`
- `PUT /api/auth/tenant-rbac/` as `OWNER` -> `200`
- `PUT invalid resource` as `OWNER` -> `400`
