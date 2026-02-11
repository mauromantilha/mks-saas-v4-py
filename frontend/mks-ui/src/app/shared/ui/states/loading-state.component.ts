import { CommonModule } from "@angular/common";
import { Component, Input } from "@angular/core";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";

@Component({
  selector: "app-loading-state",
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule],
  template: `
    <div class="state loading" [class.compact]="compact">
      <mat-progress-spinner mode="indeterminate" [diameter]="diameter" [strokeWidth]="3"></mat-progress-spinner>
      <span>{{ message }}</span>
    </div>
  `,
  styles: [
    `
      .state.loading {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px;
        border-radius: 12px;
        border: 1px dashed var(--mks-border);
        background: color-mix(in srgb, var(--mks-surface) 95%, transparent);
      }

      .state.loading.compact {
        padding: 8px 0;
        border: 0;
        background: transparent;
      }
    `,
  ],
})
export class LoadingStateComponent {
  @Input() message = "Carregando...";
  @Input() diameter = 32;
  @Input() compact = false;
}

