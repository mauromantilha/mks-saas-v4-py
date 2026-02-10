import { Component, OnInit } from '@angular/core';
import { TableColumn } from './shared/components/app-table.component';
import { of, throwError } from 'rxjs';
import { delay, catchError } from 'rxjs/operators';

@Component({
  selector: 'app-dummy-table',
  template: `
    <div class="p-20">
      <h2>Exemplo de Tabela (Shared UI)</h2>
      
      <div class="mb-20">
        <button mat-raised-button (click)="loadData()">Recarregar Sucesso</button>
        <button mat-raised-button color="warn" (click)="loadError()">Simular Erro</button>
        <button mat-raised-button (click)="loadEmpty()">Simular Vazio</button>
      </div>

      <app-filter-bar (search)="loadData()" (clear)="loadData()">
        <mat-form-field appearance="outline" class="compact-field">
          <mat-label>Buscar</mat-label>
          <input matInput placeholder="Nome ou ID">
        </mat-form-field>
        <mat-form-field appearance="outline" class="compact-field">
          <mat-label>Status</mat-label>
          <mat-select><mat-option value="active">Ativo</mat-option></mat-select>
        </mat-form-field>
      </app-filter-bar>

      <app-table 
        [columns]="columns" 
        [data]="data" 
        [isLoading]="isLoading" 
        [error]="error"
        [showExport]="true"
        exportFileName="usuarios_dummy"
        (rowClick)="onRowClick($event)"
        (retry)="loadData()">
        
        <div table-actions>
          <button mat-flat-button color="primary">Novo Registro</button>
        </div>
      </app-table>

      <div class="mt-40">
        <h2>Exemplo de Form Wrapper</h2>
        <app-form-wrapper title="Cadastro de Usuário">
          <div header-actions>
            <button mat-icon-button><mat-icon>help_outline</mat-icon></button>
          </div>
          
          <form class="dummy-form">
            <mat-form-field appearance="outline" class="w-100">
              <mat-label>Nome Completo</mat-label>
              <input matInput placeholder="Ex: João Silva">
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="w-100">
              <mat-label>Email</mat-label>
              <input matInput placeholder="Ex: joao@email.com">
            </mat-form-field>
          </form>

          <div footer-actions>
            <button mat-button>Cancelar</button>
            <button mat-raised-button color="primary">Salvar</button>
          </div>
        </app-form-wrapper>
      </div>
    </div>
  `,
  styles: [`
    .mt-40 { margin-top: 40px; }
    .w-100 { width: 100%; }
    .dummy-form { display: flex; flex-direction: column; gap: 10px; }
    .compact-field { width: 200px; font-size: 14px; }
  `]
})
export class DummyTableComponent implements OnInit {
  columns: TableColumn[] = [
    { def: 'id', label: 'ID' },
    { def: 'name', label: 'Nome' },
    { def: 'role', label: 'Cargo' },
    { def: 'status', label: 'Status' },
    { def: 'created_at', label: 'Data Criação', format: (row) => new Date(row.created_at).toLocaleDateString() }
  ];

  data: any[] = [];
  isLoading = false;
  error: string | null = null;

  ngOnInit() {
    this.loadData();
  }

  loadData() {
    this.isLoading = true;
    this.error = null;
    this.data = [];
    
    // Simulate API call
    of([
      { id: 1, name: 'João Silva', role: 'Admin', status: 'Ativo', created_at: '2023-01-01' },
      { id: 2, name: 'Maria Santos', role: 'User', status: 'Inativo', created_at: '2023-02-15' },
      { id: 3, name: 'Carlos Oliveira', role: 'Manager', status: 'Ativo', created_at: '2023-03-10' },
      { id: 4, name: 'Ana Costa', role: 'User', status: 'Pendente', created_at: '2023-04-05' },
      { id: 5, name: 'Pedro Souza', role: 'User', status: 'Ativo', created_at: '2023-05-20' },
    ]).pipe(delay(1500)).subscribe(res => {
      this.data = res;
      this.isLoading = false;
    });
  }

  loadError() {
    this.isLoading = true;
    this.error = null;
    this.data = [];
    
    throwError(() => new Error('Falha ao conectar com o servidor.')).pipe(
      delay(1500),
      catchError(err => {
        this.error = err.message;
        this.isLoading = false;
        return of([]);
      })
    ).subscribe();
  }

  loadEmpty() {
    this.isLoading = true;
    this.error = null;
    this.data = [];
    of([]).pipe(delay(1000)).subscribe(res => {
      this.data = res;
      this.isLoading = false;
    });
  }

  onRowClick(row: any) {
    console.log('Row clicked:', row);
  }
}