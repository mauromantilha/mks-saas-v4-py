import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, Output } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";

@Component({
  selector: "app-error-state",
  standalone: true,
  imports: [CommonModule, MatIconModule, MatButtonModule],
  template: `
    <div class="state error" [class.compact]="compact">
      <mat-icon>error_outline</mat-icon>
      <span>{{ message }}</span>
      <button mat-stroked-button type="button" *ngIf="retryLabel" (click)="retry.emit()">
        {{ retryLabel }}
      </button>
    </div>
  `,
  styles: [
    `
      .state.error {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px;
        border-radius: 12px;
        border: 1px dashed color-mix(in srgb, #f04438 42%, var(--mks-border));
        color: #f04438;
      }

      .state.error.compact {
        padding: 8px 0;
        border: 0;
      }
    `,
  ],
})
export class ErrorStateComponent {
  @Input() message = "Ocorreu um erro ao carregar os dados.";
  @Input() retryLabel = "Tentar novamente";
  @Input() compact = false;
  @Output() retry = new EventEmitter<void>();
}

