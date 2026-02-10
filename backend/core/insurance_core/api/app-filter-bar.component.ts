import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-filter-bar',
  template: `
    <div class="filter-bar mat-elevation-z1">
      <div class="filter-content">
        <ng-content></ng-content>
      </div>
      <div class="filter-actions" *ngIf="showActions">
        <button mat-button (click)="onClear()">Limpar</button>
        <button mat-raised-button color="primary" (click)="onSearch()">
          <mat-icon>search</mat-icon> Filtrar
        </button>
      </div>
    </div>
  `,
  styles: [`
    .filter-bar {
      background: white;
      border-radius: 4px;
      padding: 16px;
      margin-bottom: 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
    }
    .filter-content {
      flex: 1;
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
    }
    .filter-actions { display: flex; gap: 8px; margin-left: auto; }
  `]
})
export class AppFilterBarComponent {
  @Input() showActions = true;
  @Output() search = new EventEmitter<void>();
  @Output() clear = new EventEmitter<void>();

  onSearch() { this.search.emit(); }
  onClear() { this.clear.emit(); }
}