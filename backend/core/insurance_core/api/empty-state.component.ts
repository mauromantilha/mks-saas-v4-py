import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-empty-state',
  template: `
    <div class="empty-container">
      <mat-icon class="icon">{{ icon }}</mat-icon>
      <h3>{{ title }}</h3>
      <p>{{ message }}</p>
    </div>
  `,
  styles: [`
    .empty-container { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; color: #888; text-align: center; }
    .icon { font-size: 48px; height: 48px; width: 48px; margin-bottom: 10px; opacity: 0.5; }
    h3 { margin: 0 0 5px 0; font-weight: 500; }
    p { margin: 0; font-size: 0.9rem; }
  `]
})
export class EmptyStateComponent {
  @Input() icon = 'inbox';
  @Input() title = 'Nenhum dado encontrado';
  @Input() message = 'Não há registros para exibir no momento.';
}