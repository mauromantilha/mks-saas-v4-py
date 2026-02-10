import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, BehaviorSubject, combineLatest } from 'rxjs';
import { debounceTime, distinctUntilChanged, map, switchMap, tap, startWith } from 'rxjs/operators';
import { PolicyService, Policy, PolicyListParams } from '../policy.service';
import { PermissionService } from '../core/services/permission.service';
import { TableColumn } from '../app-table.component';

@Component({
  selector: 'app-policy-list',
  template: `
    <div class="policy-list-container">
      <div class="header">
        <h1>Apólices</h1>
        <button *appHasPermission="'policy.create'" (click)="createPolicy()" class="btn-primary">Nova Apólice</button>
      </div>

      <app-filter-bar (search)="refresh()" (clear)="clearFilters()">
        <form [formGroup]="filterForm" class="filter-form">
          <mat-form-field appearance="outline" class="search-input">
            <mat-label>Buscar</mat-label>
            <input matInput formControlName="search" placeholder="Número ou cliente...">
            <mat-icon matSuffix>search</mat-icon>
          </mat-form-field>
          
          <mat-form-field appearance="outline">
            <mat-label>Status</mat-label>
            <mat-select formControlName="status">
              <mat-option value="">Todos</mat-option>
              <mat-option value="QUOTED">Cotação</mat-option>
              <mat-option value="ISSUED">Emitida</mat-option>
              <mat-option value="ACTIVE">Ativa</mat-option>
              <mat-option value="CANCELLED">Cancelada</mat-option>
              <mat-option value="EXPIRED">Expirada</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline" class="small-input">
            <mat-label>Ramo (ID)</mat-label>
            <input matInput type="number" formControlName="branch_id">
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Vigência (De)</mat-label>
            <input matInput type="date" formControlName="start_date_after">
          </mat-form-field>
        </form>
      </app-filter-bar>

      <app-table
        [columns]="columns"
        [data]="(policies$ | async) || []"
        [isLoading]="isLoading"
        [showFilter]="false"
        (rowClick)="onRowClick($event)">
      </app-table>
    </div>
  `,
  styles: [`
    .policy-list-container { padding: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .filter-form { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; width: 100%; }
    .search-input { width: 300px; }
    .small-input { width: 120px; }
    /* Compact form fields */
    ::ng-deep .filter-form .mat-mdc-form-field-subscript-wrapper { display: none; }
  `]
})
export class PolicyListComponent implements OnInit {
  filterForm: FormGroup;
  policies$: Observable<Policy[]>;
  isLoading = false;
  
  columns: TableColumn[] = [
    { def: 'policy_number', label: 'Número' },
    { def: 'customer', label: 'Segurado', format: (row) => row.customer?.name },
    { def: 'insurer', label: 'Seguradora', format: (row) => row.insurer?.name },
    { def: 'product', label: 'Produto', format: (row) => row.product?.name },
    { def: 'dates', label: 'Vigência', format: (row) => `${new Date(row.start_date).toLocaleDateString()} - ${new Date(row.end_date).toLocaleDateString()}` },
    { def: 'status', label: 'Status' },
    { def: 'premium_total', label: 'Prêmio', format: (row) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(row.premium_total) },
  ];
  
  private refreshSubject = new BehaviorSubject<void>(undefined);

  constructor(private fb: FormBuilder, private policyService: PolicyService, private permissionService: PermissionService, private router: Router, private route: ActivatedRoute) {
    this.filterForm = this.fb.group({ search: [''], status: [''], branch_id: [''], insurer_id: [''], start_date_after: [''], start_date_before: [''] });
  }

  ngOnInit(): void {
    const filters$ = this.filterForm.valueChanges.pipe(startWith(this.filterForm.value), debounceTime(300), distinctUntilChanged((p, c) => JSON.stringify(p) === JSON.stringify(c)), tap(() => this.currentPage = 1));
    
    this.policies$ = combineLatest([filters$, this.refreshSubject]).pipe(
      tap(() => this.isLoading = true),
      switchMap(([filters]) => {
        const params: PolicyListParams = { ...filters };
        Object.keys(params).forEach(key => (params as any)[key] === '' && delete (params as any)[key]);
        return this.policyService.list(params).pipe(
          map(res => res.results || []),
          tap(() => this.isLoading = false)
        );
      })
    );
  }

  refresh() { this.refreshSubject.next(); }
  clearFilters() { this.filterForm.reset(); }
  createPolicy(): void { this.router.navigate(['new'], { relativeTo: this.route }); }
  onRowClick(row: Policy) { this.router.navigate([row.id], { relativeTo: this.route }); }
}