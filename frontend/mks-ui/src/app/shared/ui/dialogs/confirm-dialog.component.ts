import { CommonModule } from "@angular/common";
import { Component, Inject } from "@angular/core";
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";

export interface ConfirmDialogData {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmColor?: "primary" | "accent" | "warn";
  reasonLabel?: string;
  reasonRequired?: boolean;
  requireText?: string;
  requireTextLabel?: string;
}

export interface ConfirmDialogResult {
  confirmed: boolean;
  reason: string;
  confirmationText: string;
}

@Component({
  selector: "app-confirm-dialog",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>

    <mat-dialog-content>
      <p class="message">{{ data.message }}</p>

      <form [formGroup]="form" class="dialog-form">
        <mat-form-field appearance="outline" *ngIf="data.reasonLabel">
          <mat-label>{{ data.reasonLabel }}</mat-label>
          <textarea matInput rows="3" formControlName="reason"></textarea>
          <mat-error *ngIf="form.controls.reason.touched && form.controls.reason.hasError('required')">
            Informe o motivo.
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="outline" *ngIf="data.requireText">
          <mat-label>{{ data.requireTextLabel || "Confirmação" }}</mat-label>
          <input matInput formControlName="confirmationText" [placeholder]="data.requireText" />
          <mat-error
            *ngIf="form.controls.confirmationText.touched && form.controls.confirmationText.hasError('required')"
          >
            Campo obrigatório.
          </mat-error>
          <mat-error
            *ngIf="form.controls.confirmationText.touched && form.controls.confirmationText.hasError('mismatch')"
          >
            O valor informado não confere.
          </mat-error>
        </mat-form-field>
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-stroked-button type="button" (click)="cancel()">
        {{ data.cancelLabel || "Cancelar" }}
      </button>
      <button mat-flat-button [color]="data.confirmColor || 'primary'" type="button" (click)="confirm()">
        {{ data.confirmLabel || "Confirmar" }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .message {
        margin: 0 0 10px;
      }

      .dialog-form {
        display: flex;
        flex-direction: column;
        gap: 10px;
        min-width: min(560px, 90vw);
      }
    `,
  ],
})
export class ConfirmDialogComponent {
  readonly form = new FormGroup({
    reason: new FormControl<string>(""),
    confirmationText: new FormControl<string>(""),
  });

  constructor(
    @Inject(MAT_DIALOG_DATA) readonly data: ConfirmDialogData,
    private readonly dialogRef: MatDialogRef<ConfirmDialogComponent, ConfirmDialogResult>
  ) {
    if (data.reasonRequired) {
      this.form.controls.reason.addValidators([Validators.required]);
    }
    if (data.requireText) {
      this.form.controls.confirmationText.addValidators([Validators.required]);
    }
    this.form.updateValueAndValidity({ emitEvent: false });
  }

  cancel(): void {
    this.dialogRef.close({ confirmed: false, reason: "", confirmationText: "" });
  }

  confirm(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      return;
    }
    const reason = (this.form.controls.reason.value || "").trim();
    const confirmationText = (this.form.controls.confirmationText.value || "").trim();

    if (this.data.requireText && confirmationText !== this.data.requireText) {
      this.form.controls.confirmationText.setErrors({
        ...(this.form.controls.confirmationText.errors ?? {}),
        mismatch: true,
      });
      return;
    }

    this.dialogRef.close({
      confirmed: true,
      reason,
      confirmationText,
    });
  }
}

