import { CommonModule } from "@angular/common";
import { Component, Inject } from "@angular/core";
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";

export interface ControlPanelConfirmDialogData {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmColor?: "primary" | "accent" | "warn";
  requireSlug?: string;
  reasonLabel?: string;
  reasonRequired?: boolean;
}

export interface ControlPanelConfirmDialogResult {
  confirmed: boolean;
  reason: string;
  confirmSlug: string;
}

@Component({
  selector: "app-control-panel-confirm-dialog",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: "./control-panel-confirm-dialog.component.html",
  styleUrl: "./control-panel-confirm-dialog.component.scss",
})
export class ControlPanelConfirmDialogComponent {
  readonly form = new FormGroup({
    reason: new FormControl<string>(""),
    confirmSlug: new FormControl<string>(""),
  });

  constructor(
    @Inject(MAT_DIALOG_DATA) readonly data: ControlPanelConfirmDialogData,
    private readonly dialogRef: MatDialogRef<
      ControlPanelConfirmDialogComponent,
      ControlPanelConfirmDialogResult
    >
  ) {
    if (data.reasonRequired) {
      this.form.controls.reason.addValidators([Validators.required]);
    }
    if (data.requireSlug) {
      this.form.controls.confirmSlug.addValidators([Validators.required]);
    }
    this.form.updateValueAndValidity({ emitEvent: false });
  }

  cancel(): void {
    this.dialogRef.close({ confirmed: false, reason: "", confirmSlug: "" });
  }

  confirm(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      return;
    }

    const reason = (this.form.controls.reason.value || "").trim();
    const confirmSlug = (this.form.controls.confirmSlug.value || "").trim();

    if (this.data.requireSlug && confirmSlug !== this.data.requireSlug) {
      this.form.controls.confirmSlug.setErrors({
        ...(this.form.controls.confirmSlug.errors ?? {}),
        mismatch: true,
      });
      return;
    }

    this.dialogRef.close({ confirmed: true, reason, confirmSlug });
  }
}
