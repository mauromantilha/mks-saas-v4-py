import { bootstrapApplication } from "@angular/platform-browser";

import { AppComponent } from "./app/app.component";
import { appConfig } from "./app/app.config";
import { installMatFormFieldRuntimeGuard } from "./app/core/material/mat-form-field-runtime-guard";

installMatFormFieldRuntimeGuard();

bootstrapApplication(AppComponent, appConfig).catch((err) =>
  console.error(err)
);
