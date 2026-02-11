import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, Output } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";

@Component({
  selector: "app-empty-state",
  standalone: true,
  imports: [CommonModule, MatIconModule, MatButtonModule],
  template: `
    <div class="state empty" [class.compact]="compact">
      <mat-icon>{{ icon }}</mat-icon>
      <div class="content">
        <div class="title">{{ title }}</div>
        <div class="description" *ngIf="description">{{ description }}</div>
      </div>
      <button mat-stroked-button type="button" *ngIf="actionLabel" (click)="action.emit()">
        {{ actionLabel }}
      </button>
    </div>
  `,
  styles: [
    `
      .state.empty {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px;
        border-radius: 12px;
        border: 1px dashed var(--mks-border);
        color: var(--mks-text-muted);
      }

      .state.empty.compact {
        padding: 8px 0;
        border: 0;
      }

      .content {
        display: grid;
        gap: 2px;
      }

      .title {
        font-weight: 600;
        color: var(--mks-text);
      }
    `,
  ],
})
export class EmptyStateComponent {
  @Input() icon = "inbox";
  @Input() title = "Sem dados";
  @Input() description = "";
  @Input() actionLabel = "";
  @Input() compact = false;
  @Output() action = new EventEmitter<void>();
}

