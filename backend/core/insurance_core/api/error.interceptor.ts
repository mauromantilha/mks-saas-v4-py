import { Injectable } from '@angular/core';
import { HttpRequest, HttpHandler, HttpEvent, HttpInterceptor, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { AuthService } from './auth.service';
import { ToastService } from './toast.service';

@Injectable()
export class ErrorInterceptor implements HttpInterceptor {
  constructor(private authService: AuthService, private toastService: ToastService) {}

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    return next.handle(request).pipe(
      catchError((error: HttpErrorResponse) => {
        let errorMessage = 'An unknown error occurred!';
        const correlationId = error.headers.get('X-Correlation-ID') || request.headers.get('X-Correlation-ID') || 'N/A';
        
        if (error.error instanceof ErrorEvent) {
          // Erro client-side
          errorMessage = `Error: ${error.error.message}`;
        } else {
          // Erro server-side
          if (error.status === 401) {
            this.authService.logout();
            errorMessage = 'Sessão expirada. Por favor, faça login novamente.';
          } else if (error.status === 403) {
            errorMessage = 'Você não tem permissão para acessar este recurso.';
          } else if (error.status === 422) {
            errorMessage = 'Erro de validação. Verifique os dados enviados.';
          } else {
            errorMessage = `Error Code: ${error.status}\nMessage: ${error.message}`;
          }
        }

        // Show Snackbar
        this.toastService.error(errorMessage);

        // Add Correlation ID for support
        const detailedError = `${errorMessage}\nCorrelation ID: ${correlationId}`;
        return throwError(() => new Error(detailedError));
      })
    );
  }
}