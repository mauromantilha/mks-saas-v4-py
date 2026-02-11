import { MatFormField } from "@angular/material/form-field";
import { Subject } from "rxjs";

type MatFormFieldLike = {
  _control?: unknown;
  _elementRef?: { nativeElement?: HTMLElement };
  _assertFormFieldControl?: () => void;
  _initializeControl?: () => void;
  ngAfterContentChecked?: () => void;
  ngOnDestroy?: () => void;
  __mksFallbackControl?: FallbackFormFieldControl;
};

type FallbackFormFieldControl = {
  value: null;
  stateChanges: Subject<void>;
  id: string;
  placeholder: string;
  ngControl: null;
  focused: boolean;
  empty: boolean;
  shouldLabelFloat: boolean;
  required: boolean;
  disabled: boolean;
  errorState: boolean;
  controlType: string;
  autofilled: boolean;
  userAriaDescribedBy: string;
  setDescribedByIds: (_ids: string[]) => void;
  onContainerClick: (_event: MouseEvent) => void;
};

function sanitizeLabel(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function createFallbackControl(label: string): FallbackFormFieldControl {
  const normalized = sanitizeLabel(label) || "field";
  return {
    value: null,
    stateChanges: new Subject<void>(),
    id: `mks-fallback-${normalized}`,
    placeholder: "",
    ngControl: null,
    focused: false,
    empty: true,
    shouldLabelFloat: false,
    required: false,
    disabled: true,
    errorState: false,
    controlType: "mks-fallback",
    autofilled: false,
    userAriaDescribedBy: "",
    setDescribedByIds: () => undefined,
    onContainerClick: () => undefined,
  };
}

export function installMatFormFieldRuntimeGuard(): void {
  const proto = MatFormField.prototype as unknown as MatFormFieldLike & {
    __mksPatched?: boolean;
  };

  if (proto.__mksPatched) {
    return;
  }
  proto.__mksPatched = true;

  const originalAssert = proto._assertFormFieldControl;
  const originalInitialize = proto._initializeControl;
  const originalAfterContentChecked = proto.ngAfterContentChecked;
  const originalDestroy = proto.ngOnDestroy;

  const ensureControl = (ctx: MatFormFieldLike): void => {
    if (ctx._control) {
      return;
    }

    if (!ctx.__mksFallbackControl) {
      const host = ctx._elementRef?.nativeElement;
      const label = host?.querySelector("mat-label")?.textContent?.trim() || "unknown";
      ctx.__mksFallbackControl = createFallbackControl(label);
      // No PII in this log: only field label and route pathname.
      // Helps locate template issues in production without blank-screen crash.
      const routePath =
        typeof window !== "undefined" ? window.location.pathname : "server";
      console.warn("[MKS] MatFormField fallback applied", {
        label,
        route: routePath,
      });
    }
    ctx._control = ctx.__mksFallbackControl;
  };

  proto._assertFormFieldControl = function patchedAssert(this: MatFormFieldLike): void {
    ensureControl(this);
    if (typeof originalAssert === "function") {
      originalAssert.apply(this);
    }
  };

  proto._initializeControl = function patchedInitialize(this: MatFormFieldLike): void {
    ensureControl(this);
    if (typeof originalInitialize === "function") {
      originalInitialize.apply(this);
    }
  };

  proto.ngAfterContentChecked = function patchedAfterContentChecked(this: MatFormFieldLike): void {
    ensureControl(this);
    if (typeof originalAfterContentChecked === "function") {
      originalAfterContentChecked.apply(this);
    }
  };

  proto.ngOnDestroy = function patchedOnDestroy(this: MatFormFieldLike): void {
    this.__mksFallbackControl?.stateChanges.complete();
    if (typeof originalDestroy === "function") {
      originalDestroy.apply(this);
    }
  };
}
