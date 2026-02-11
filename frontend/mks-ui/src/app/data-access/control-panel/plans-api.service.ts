import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import { PlanDto, TenantDto, TenantSubscriptionUpdateDto } from "./control-panel.dto";

@Injectable({ providedIn: "root" })
export class PlansApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly plansUrl = buildApiUrl(this.config, "/control-panel/plans/");
  private readonly tenantsUrl = buildApiUrl(this.config, "/control-panel/tenants/");

  listPlans(): Observable<PlanDto[]> {
    return this.http.get<PlanDto[]>(this.plansUrl);
  }

  updateTenantSubscription(
    tenantId: number,
    dto: TenantSubscriptionUpdateDto
  ): Observable<TenantDto> {
    return this.http.post<TenantDto>(`${this.tenantsUrl}${tenantId}/subscription/`, dto);
  }
}

