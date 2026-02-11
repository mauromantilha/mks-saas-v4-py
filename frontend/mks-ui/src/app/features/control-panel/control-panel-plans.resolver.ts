import { inject } from "@angular/core";
import { ResolveFn } from "@angular/router";
import { catchError, of } from "rxjs";

import { PlanDto } from "../../data-access/control-panel";
import { PlansApi } from "../../data-access/control-panel/plans-api.service";

export const controlPanelPlansResolver: ResolveFn<PlanDto[]> = () => {
  const plansApi = inject(PlansApi);
  return plansApi.listPlans().pipe(catchError(() => of([])));
};
