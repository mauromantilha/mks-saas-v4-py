type ErrorEventEntry = {
  at: string;
  type: "window.error" | "window.unhandledrejection" | "fetch.error" | "fetch.http";
  message: string;
  source?: string;
  stack?: string;
  status?: number;
  method?: string;
  url?: string;
};

declare global {
  interface Window {
    __mksErrorProbeInstalled?: boolean;
    __mksErrorEvents?: ErrorEventEntry[];
    __mksDumpErrors?: () => ErrorEventEntry[];
  }
}

function sanitizeUrl(input: string): string {
  try {
    const url = new URL(input, window.location.origin);
    return `${url.origin}${url.pathname}`;
  } catch {
    return input.split("?")[0] || input;
  }
}

function pushEvent(entry: ErrorEventEntry): void {
  const list = (window.__mksErrorEvents ??= []);
  list.push(entry);
  if (list.length > 200) {
    list.shift();
  }
}

export function installRuntimeErrorProbe(): void {
  if (typeof window === "undefined" || window.__mksErrorProbeInstalled) {
    return;
  }
  window.__mksErrorProbeInstalled = true;
  window.__mksErrorEvents = window.__mksErrorEvents ?? [];
  window.__mksDumpErrors = () => [...(window.__mksErrorEvents ?? [])];

  window.addEventListener("error", (event) => {
    pushEvent({
      at: new Date().toISOString(),
      type: "window.error",
      message: event.message || "Unknown error",
      source: sanitizeUrl(event.filename || ""),
      stack: (event.error as Error | undefined)?.stack,
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    const message =
      reason instanceof Error
        ? reason.message
        : typeof reason === "string"
          ? reason
          : "Unhandled promise rejection";

    pushEvent({
      at: new Date().toISOString(),
      type: "window.unhandledrejection",
      message,
      stack: reason instanceof Error ? reason.stack : undefined,
    });
  });

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args: Parameters<typeof fetch>) => {
    const request = args[0];
    const isRequestObject = typeof Request !== "undefined" && request instanceof Request;
    const isUrlObject = typeof URL !== "undefined" && request instanceof URL;
    const method = isRequestObject
      ? request.method.toUpperCase()
      : (args[1]?.method || "GET").toUpperCase();
    const url = isRequestObject
      ? request.url
      : isUrlObject
        ? request.toString()
        : String(request);
    try {
      const response = await originalFetch(...args);
      if (!response.ok) {
        pushEvent({
          at: new Date().toISOString(),
          type: "fetch.http",
          message: `HTTP ${response.status}`,
          status: response.status,
          method,
          url: sanitizeUrl(url),
        });
      }
      return response;
    } catch (error) {
      const err = error as Error;
      pushEvent({
        at: new Date().toISOString(),
        type: "fetch.error",
        message: err?.message || "Fetch failed",
        stack: err?.stack,
        method,
        url: sanitizeUrl(url),
      });
      throw error;
    }
  };
}
