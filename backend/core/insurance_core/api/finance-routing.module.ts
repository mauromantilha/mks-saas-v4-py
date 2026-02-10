import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { PermissionGuard } from '../../core/guards/permission.guard';
// Import components
import { FinanceInstallmentsComponent } from './receivables/receivables.component';
import { PayablesComponent } from './payables/payables.component';
import { LedgerComponent } from './ledger/ledger.component';
import { BankingComponent } from './banking/banking.component';
import { FinanceDashboardComponent } from './dashboard/finance-dashboard.component';

const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: FinanceDashboardComponent, data: { permission: 'finance.dashboard.view' }, canActivate: [PermissionGuard] },
  { path: 'receivables', component: FinanceInstallmentsComponent, data: { permission: 'finance.receivables.view' }, canActivate: [PermissionGuard] },
  { path: 'payables', component: PayablesComponent, data: { permission: 'finance.payables.view' }, canActivate: [PermissionGuard] },
  { path: 'ledger', component: LedgerComponent, data: { permission: 'finance.ledger.view' }, canActivate: [PermissionGuard] },
  { path: 'banking', component: BankingComponent, data: { permission: 'finance.banking.view' }, canActivate: [PermissionGuard] },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class FinanceRoutingModule { }