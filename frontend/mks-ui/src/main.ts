import { bootstrapApplication } from "@angular/platform-browser";

import { AppComponent } from "./app/app.component";
import { appConfig } from "./app/app.config";
import { installRuntimeErrorProbe } from "./app/core/debug/runtime-error-probe";
import { installMatFormFieldRuntimeGuard } from "./app/core/material/mat-form-field-runtime-guard";

installRuntimeErrorProbe();
installMatFormFieldRuntimeGuard();

bootstrapApplication(AppComponent, appConfig).catch((err) =>
  console.error(err)
);
