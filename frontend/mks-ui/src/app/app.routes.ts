import { Routes } from "@angular/router";

import { authGuard } from "./core/auth/auth.guard";
import { LoginPageComponent } from "./features/auth/login-page.component";
import { SalesFlowPageComponent } from "./features/sales/sales-flow-page.component";
import { TenantMembersPageComponent } from "./features/tenant-settings/tenant-members-page.component";
import { TenantRbacPageComponent } from "./features/tenant-settings/tenant-rbac-page.component";

export const routes: Routes = [
  { path: "", pathMatch: "full", redirectTo: "login" },
  { path: "login", component: LoginPageComponent },
  { path: "sales/flow", component: SalesFlowPageComponent, canActivate: [authGuard] },
  { path: "tenant/members", component: TenantMembersPageComponent, canActivate: [authGuard] },
  { path: "tenant/rbac", component: TenantRbacPageComponent, canActivate: [authGuard] },
  { path: "**", redirectTo: "login" },
];
