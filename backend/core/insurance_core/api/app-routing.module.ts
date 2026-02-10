import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { LayoutComponent } from './layout/layout.component';
import { AuthGuard } from './core/guards/auth.guard';

const routes: Routes = [
  {
    path: '',
    component: LayoutComponent,
    canActivate: [AuthGuard],
    children: [
      { path: '', redirectTo: 'policies', pathMatch: 'full' },
      { 
        path: 'policies', 
        loadChildren: () => import('./features/policy/policy.module').then(m => m.PolicyModule) 
      },
      { 
        path: 'finance', 
        loadChildren: () => import('./features/finance/finance.module').then(m => m.FinanceModule) 
      },
      { 
        path: 'commission', 
        loadChildren: () => import('./features/commission/commission.module').then(m => m.CommissionModule) 
      },
      { 
        path: 'documents', 
        loadChildren: () => import('./features/documents/documents.module').then(m => m.DocumentsModule) 
      },
      { 
        path: 'claims', 
        loadChildren: () => import('./features/claims/claims.module').then(m => m.ClaimsModule) 
      },
    ]
  },
  { path: 'login', loadChildren: () => import('./core/auth/auth.module').then(m => m.AuthModule) },
  { path: '**', redirectTo: '' }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }