import { ErrorHandler, Injectable } from "@angular/core";

const CHUNK_RELOAD_GUARD_KEY = "mks_chunk_reload_guard_v1";

@Injectable()
export class GlobalErrorHandler implements ErrorHandler {
  handleError(error: unknown): void {
    const message = this.extractMessage(error);
    if (this.isChunkLoadError(message)) {
      this.reloadOnce();
      return;
    }
    // Keep stack traces available for debugging in production incidents.
    // eslint-disable-next-line no-console
    console.error(error);
  }

  private extractMessage(error: unknown): string {
    if (typeof error === "string") {
      return error;
    }
    if (error && typeof error === "object") {
      const anyError = error as {
        message?: string;
        rejection?: { message?: string };
        ngOriginalError?: { message?: string };
      };
      return (
        anyError.message ||
        anyError.rejection?.message ||
        anyError.ngOriginalError?.message ||
        ""
      );
    }
    return "";
  }

  private isChunkLoadError(message: string): boolean {
    if (!message) {
      return false;
    }
    return (
      message.includes("ChunkLoadError") ||
      message.includes("Loading chunk") ||
      message.includes("Failed to fetch dynamically imported module") ||
      message.includes("Importing a module script failed")
    );
  }

  private reloadOnce(): void {
    try {
      if (typeof window === "undefined" || typeof sessionStorage === "undefined") {
        return;
      }
      const alreadyRetried = sessionStorage.getItem(CHUNK_RELOAD_GUARD_KEY) === "1";
      if (alreadyRetried) {
        return;
      }
      sessionStorage.setItem(CHUNK_RELOAD_GUARD_KEY, "1");
      window.location.reload();
    } catch {
      // Ignore storage/reload errors in restricted browsers.
    }
  }
}
