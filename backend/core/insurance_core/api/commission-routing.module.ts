import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { PermissionGuard } from '../../core/guards/permission.guard';
// Import components
import { AccrualsComponent } from './accruals/accruals.component';
import { PayoutBatchesComponent } from './payout-batches/payout-batches.component';
import { InsurerSettlementsComponent } from './insurer-settlements/insurer-settlements.component';
import { CommissionPlansComponent } from './plans/plans.component';

const routes: Routes = [
  { path: '', redirectTo: 'accruals', pathMatch: 'full' },
  { path: 'accruals', component: AccrualsComponent, data: { permission: 'commission.accruals.view' }, canActivate: [PermissionGuard] },
  { path: 'payout-batches', component: PayoutBatchesComponent, data: { permission: 'commission.payouts.view' }, canActivate: [PermissionGuard] },
  { path: 'insurer-settlements', component: InsurerSettlementsComponent, data: { permission: 'commission.settlements.view' }, canActivate: [PermissionGuard] },
  { path: 'plans', component: CommissionPlansComponent, data: { permission: 'commission.plans.view' }, canActivate: [PermissionGuard] },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class CommissionRoutingModule { }