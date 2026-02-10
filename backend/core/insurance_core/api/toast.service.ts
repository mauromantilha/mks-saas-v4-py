import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

@Injectable({
  providedIn: 'root'
})
export class ToastService {
  constructor(private snackBar: MatSnackBar) {}

  success(message: string, action: string = 'OK', duration: number = 3000) {
    this.snackBar.open(message, action, {
      duration,
      panelClass: ['toast-success'],
      horizontalPosition: 'end',
      verticalPosition: 'top'
    });
  }

  error(message: string, action: string = 'Fechar', duration: number = 5000) {
    this.snackBar.open(message, action, {
      duration,
      panelClass: ['toast-error'],
      horizontalPosition: 'end',
      verticalPosition: 'top'
    });
  }

  info(message: string) {
    this.snackBar.open(message, 'OK', { duration: 3000, horizontalPosition: 'end', verticalPosition: 'top' });
  }
}