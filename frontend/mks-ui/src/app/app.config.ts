import { importProvidersFrom } from "@angular/core";
import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { ApplicationConfig, ErrorHandler } from "@angular/core";
import { MatSnackBarModule } from "@angular/material/snack-bar";
import { provideAnimations } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { authorizationInterceptor } from "./core/auth/authorization.interceptor";
import { provideApiConfig } from "./core/config/api-config";
import { GlobalErrorHandler } from "./core/errors/global-error-handler";
import { correlationIdInterceptor } from "./core/http/correlation-id.interceptor";
import { errorInterceptor } from "./core/http/error.interceptor";
import { routes } from "./app.routes";
import { environment } from "../environments/environment";

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideAnimations(),
    importProvidersFrom(MatSnackBarModule),
    {
      provide: ErrorHandler,
      useClass: GlobalErrorHandler,
    },
    provideApiConfig({
      baseUrl: environment.apiBaseUrl ?? "",
      tenantIdHeader: environment.tenantIdHeader,
      // Backend atual usa DRF TokenAuth; trocar para "Bearer" quando backend aceitar.
      authHeaderScheme: "Token",
    }),
    provideHttpClient(
      withInterceptors([correlationIdInterceptor, authorizationInterceptor, errorInterceptor])
    ),
  ],
};
