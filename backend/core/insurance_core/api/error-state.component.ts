import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-error-state',
  template: `
    <div class="error-container">
      <mat-icon color="warn" class="icon">error_outline</mat-icon>
      <h3>Ocorreu um erro</h3>
      <p>{{ error }}</p>
      <button mat-stroked-button color="primary" (click)="retry.emit()">Tentar Novamente</button>
    </div>
  `,
  styles: [`
    .error-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; color: #666; text-align: center; }
    .icon { font-size: 48px; height: 48px; width: 48px; margin-bottom: 10px; }
    h3 { margin: 0 0 5px 0; font-weight: 500; }
    p { margin: 0 0 15px 0; font-size: 0.9rem; max-width: 400px; }
  `]
})
export class ErrorStateComponent {
  @Input() error: string = 'Erro desconhecido';
  @Output() retry = new EventEmitter<void>();
}