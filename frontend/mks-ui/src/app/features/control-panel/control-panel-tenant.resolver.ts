import { inject } from "@angular/core";
import { ResolveFn, Router } from "@angular/router";
import { catchError, EMPTY } from "rxjs";

import { TenantDto } from "../../data-access/control-panel";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";

export const controlPanelTenantResolver: ResolveFn<TenantDto> = (route) => {
  const tenantApi = inject(TenantApi);
  const router = inject(Router);
  const tenantId = Number(route.paramMap.get("id"));

  if (!Number.isFinite(tenantId) || tenantId <= 0) {
    void router.navigate(["/control-panel/tenants"]);
    return EMPTY;
  }

  return tenantApi.getTenant(tenantId).pipe(
    catchError(() => {
      void router.navigate(["/control-panel/tenants"]);
      return EMPTY;
    })
  );
};
