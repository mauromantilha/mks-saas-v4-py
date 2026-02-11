import { FormGroup } from "@angular/forms";
import { ApiErrorNormalized } from "../../core/http/api-error.util";

export type ApiValidationErrors = Record<string, string[]>;

export function applyApiValidationErrorsToForm(
  form: FormGroup,
  validationErrors: ApiValidationErrors
): string[] {
  const formLevelMessages: string[] = [];

  Object.entries(validationErrors).forEach(([field, messages]) => {
    const control = form.get(field);
    if (!control) {
      formLevelMessages.push(...messages);
      return;
    }
    control.setErrors({
      ...(control.errors ?? {}),
      api: messages.join(" "),
    });
    control.markAsTouched();
  });

  return formLevelMessages;
}

export function normalizeAndApplyApiFormError(
  form: FormGroup,
  error: unknown,
  fallbackMessage = "Não foi possível salvar os dados."
): string {
  const normalized = (error as { normalizedError?: ApiErrorNormalized })?.normalizedError;
  if (!normalized) {
    return fallbackMessage;
  }

  const formLevelMessages = applyApiValidationErrorsToForm(form, normalized.validation || {});
  if (formLevelMessages.length > 0) {
    return formLevelMessages.join(" | ");
  }
  return normalized.message || fallbackMessage;
}
