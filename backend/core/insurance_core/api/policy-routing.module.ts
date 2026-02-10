import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { PermissionGuard } from '../../core/guards/permission.guard';
import { PolicyListComponent } from './policy-list/policy-list.component';
import { PolicyFormComponent } from './policy-form/policy-form.component';
import { PolicyDetailComponent } from './policy-detail/policy-detail.component';
import { PolicyResolver } from './policy.resolver';
import { 
  PolicyOverviewComponent, 
  PolicyBillingComponent, 
  PolicyEndorsementsComponent, 
  PolicyClaimsComponent, 
  PolicyDocumentsComponent, 
  PolicyAuditComponent 
} from './policy-detail/policy-tabs.component';

const routes: Routes = [
  { 
    path: '', 
    component: PolicyListComponent,
    data: { permission: 'policy.list' },
    canActivate: [PermissionGuard]
  },
  { path: 'new', component: PolicyFormComponent, data: { permission: 'policy.create' }, canActivate: [PermissionGuard] },
  { 
    path: ':id', 
    component: PolicyDetailComponent, 
    resolve: { policy: PolicyResolver },
    data: { permission: 'policy.view' }, 
    canActivate: [PermissionGuard],
    children: [
      { path: '', redirectTo: 'overview', pathMatch: 'full' },
      { path: 'overview', component: PolicyOverviewComponent },
      { path: 'billing', component: PolicyBillingComponent },
      { path: 'endorsements', component: PolicyEndorsementsComponent },
      { path: 'claims', component: PolicyClaimsComponent },
      { path: 'documents', component: PolicyDocumentsComponent },
      { path: 'audit', component: PolicyAuditComponent }
    ]
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class PolicyRoutingModule { }