import { Component, EventEmitter, Input, Output, ViewChild, AfterViewInit, OnChanges, SimpleChanges } from '@angular/core';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { MatTableDataSource } from '@angular/material/table';

export interface TableColumn {
  def: string;
  label: string;
  format?: (row: any) => string;
  hidden?: boolean;
}

@Component({
  selector: 'app-table',
  template: `
    <div class="table-container mat-elevation-z2">
      <div class="table-toolbar" *ngIf="showFilter">
        <mat-form-field appearance="outline" class="search-field" subscriptSizing="dynamic">
          <mat-label>Filtrar</mat-label>
          <input matInput (keyup)="applyFilter($event)" placeholder="Buscar..." #input>
          <mat-icon matSuffix>search</mat-icon>
        </mat-form-field>
        <div class="actions">
          <button mat-icon-button *ngIf="showExport" (click)="exportToCsv()" title="Exportar CSV">
            <mat-icon>download</mat-icon>
          </button>
          <ng-content select="[table-actions]"></ng-content>
        </div>
      </div>

      <div class="table-wrapper">
        <div *ngIf="isLoading" class="loading-overlay">
          <app-loading-state></app-loading-state>
        </div>

        <div *ngIf="error" class="error-overlay">
          <app-error-state [error]="error" (retry)="retry.emit()"></app-error-state>
        </div>

        <table mat-table [dataSource]="dataSource" matSort [class.hidden]="isLoading || error || (dataSource.data.length === 0)">
          
          <ng-container *ngFor="let col of columns" [matColumnDef]="col.def">
            <th mat-header-cell *matHeaderCellDef mat-sort-header> {{ col.label }} </th>
            <td mat-cell *matCellDef="let row"> 
              {{ col.format ? col.format(row) : row[col.def] }} 
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="displayedColumns; sticky: true"></tr>
          <tr mat-row *matRowDef="let row; columns: displayedColumns;" (click)="rowClick.emit(row)" [class.clickable]="rowClick.observers.length > 0"></tr>
        </table>

        <app-empty-state *ngIf="!isLoading && !error && dataSource.data.length === 0"></app-empty-state>
      </div>

      <mat-paginator [pageSizeOptions]="[5, 10, 25, 100]" showFirstLastButtons></mat-paginator>
    </div>
  `,
  styles: [`
    .table-container { display: flex; flex-direction: column; background: white; border-radius: 4px; overflow: hidden; }
    .table-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; border-bottom: 1px solid rgba(0,0,0,0.12); }
    .actions { display: flex; align-items: center; gap: 8px; }
    .search-field { font-size: 14px; width: 300px; }
    .table-wrapper { position: relative; min-height: 200px; overflow: auto; }
    table { width: 100%; }
    .loading-overlay, .error-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.8); z-index: 10; display: flex; justify-content: center; align-items: center; }
    .clickable:hover { background: #f5f5f5; cursor: pointer; }
    
    /* Compact styles for ERP look */
    ::ng-deep .mat-mdc-header-row { height: 48px !important; }
    ::ng-deep .mat-mdc-row { height: 40px !important; }
    ::ng-deep .mat-mdc-cell, ::ng-deep .mat-mdc-header-cell { padding-left: 16px !important; padding-right: 16px !important; font-size: 13px; }
  `]
})
export class AppTableComponent implements AfterViewInit, OnChanges {
  @Input() columns: TableColumn[] = [];
  @Input() data: any[] = [];
  @Input() isLoading = false;
  @Input() error: string | null = null;
  @Input() showFilter = true;
  @Input() showExport = false;
  @Input() exportFileName = 'export';

  @Output() rowClick = new EventEmitter<any>();
  @Output() retry = new EventEmitter<void>();

  dataSource = new MatTableDataSource<any>([]);
  displayedColumns: string[] = [];

  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  ngOnChanges(changes: SimpleChanges) {
    if (changes['data']) {
      this.dataSource.data = this.data || [];
    }
    if (changes['columns']) {
      this.displayedColumns = this.columns.filter(c => !c.hidden).map(c => c.def);
    }
  }

  ngAfterViewInit() {
    this.dataSource.paginator = this.paginator;
    this.dataSource.sort = this.sort;
  }

  applyFilter(event: Event) {
    const filterValue = (event.target as HTMLInputElement).value;
    this.dataSource.filter = filterValue.trim().toLowerCase();
    if (this.dataSource.paginator) {
      this.dataSource.paginator.firstPage();
    }
  }

  exportToCsv() {
    const data = this.dataSource.filteredData;
    const exportColumns = this.columns.filter(c => !c.hidden);
    
    const headers = exportColumns.map(c => this.escapeCsv(c.label)).join(',');
    const rows = data.map(row => {
      return exportColumns.map(c => {
        const val = c.format ? c.format(row) : row[c.def];
        return this.escapeCsv(val);
      }).join(',');
    });

    const csvContent = '\uFEFF' + [headers, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `${this.exportFileName}_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  private escapeCsv(value: any): string {
    if (value === null || value === undefined) return '';
    let str = String(value);

    // Prevent CSV Injection (Formula Injection)
    if (['=', '+', '-', '@'].includes(str.charAt(0))) {
      str = "'" + str;
    }

    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  }
}