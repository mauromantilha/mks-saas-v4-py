import { Injectable } from "@angular/core";
import { MatSnackBar } from "@angular/material/snack-bar";

@Injectable({ providedIn: "root" })
export class ToastService {
  constructor(private readonly snackBar: MatSnackBar) {}

  success(message: string): void {
    this.open(message, "mks-toast-success");
  }

  info(message: string): void {
    this.open(message, "mks-toast-info");
  }

  warning(message: string): void {
    this.open(message, "mks-toast-warning");
  }

  error(message: string): void {
    this.open(message, "mks-toast-error", 6000);
  }

  private open(message: string, panelClass: string, duration = 4000): void {
    this.snackBar.open(message, "Fechar", {
      duration,
      panelClass: [panelClass],
      horizontalPosition: "right",
      verticalPosition: "top",
    });
  }
}

