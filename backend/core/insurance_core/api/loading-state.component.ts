import { Component } from '@angular/core';

@Component({
  selector: 'app-loading-state',
  template: `
    <div class="loading-container">
      <mat-spinner diameter="40"></mat-spinner>
      <p>Carregando dados...</p>
    </div>
  `,
  styles: [`
    .loading-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; color: #666; }
    p { margin-top: 10px; font-size: 0.9rem; }
  `]
})
export class LoadingStateComponent {}