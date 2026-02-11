import { CommonModule } from "@angular/common";
import { NgModule } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";
import { MatListModule } from "@angular/material/list";
import { MatSidenavModule } from "@angular/material/sidenav";
import { MatToolbarModule } from "@angular/material/toolbar";

import { ControlPanelCreateTenantPageComponent } from "./control-panel-create-tenant-page.component";
import { ControlPanelContractsPageComponent } from "./control-panel-contracts-page.component";
import { ControlPanelEditTenantPageComponent } from "./control-panel-edit-tenant-page.component";
import { ControlPanelLayoutComponent } from "./control-panel-layout.component";
import { ControlPanelPlansPageComponent } from "./control-panel-plans-page.component";
import { ControlPanelRoutingModule } from "./control-panel-routing.module";
import { ControlPanelSubscriptionTabComponent } from "./control-panel-subscription-tab.component";
import { ControlPanelTenantFormComponent } from "./control-panel-tenant-form.component";
import { ControlPanelTenantDetailShellComponent } from "./control-panel-tenant-detail-shell.component";
import { ControlPanelTenantsListPageComponent } from "./control-panel-tenants-list-page.component";

@NgModule({
  imports: [
    CommonModule,
    ControlPanelRoutingModule,
    ControlPanelLayoutComponent,
    ControlPanelTenantsListPageComponent,
    ControlPanelTenantFormComponent,
    ControlPanelCreateTenantPageComponent,
    ControlPanelContractsPageComponent,
    ControlPanelEditTenantPageComponent,
    ControlPanelPlansPageComponent,
    ControlPanelSubscriptionTabComponent,
    ControlPanelTenantDetailShellComponent,
    MatSidenavModule,
    MatToolbarModule,
    MatListModule,
    MatIconModule,
  ],
})
export class ControlPanelModule {}
