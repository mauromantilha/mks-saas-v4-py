import { DOCUMENT } from "@angular/common";
import { Inject, Injectable, computed, signal } from "@angular/core";

type ThemeMode = "light" | "dark";

@Injectable({ providedIn: "root" })
export class ThemeService {
  private readonly modeSignal = signal<ThemeMode>("light");
  private mediaQuery: MediaQueryList | null = null;

  readonly mode = computed(() => this.modeSignal());
  readonly isDarkMode = computed(() => this.modeSignal() === "dark");

  constructor(@Inject(DOCUMENT) private readonly document: Document) {
    this.initialize();
  }

  setDarkMode(enabled: boolean): void {
    const mode: ThemeMode = enabled ? "dark" : "light";
    this.modeSignal.set(mode);
    this.applyThemeClass(mode);
  }

  toggle(): void {
    this.setDarkMode(!this.isDarkMode());
  }

  private initialize(): void {
    const mode = this.prefersDarkMode() ? "dark" : "light";
    this.modeSignal.set(mode);
    this.applyThemeClass(mode);
    this.listenSystemThemeChanges();
  }

  private prefersDarkMode(): boolean {
    try {
      return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? false;
    } catch {
      return false;
    }
  }

  private listenSystemThemeChanges(): void {
    try {
      this.mediaQuery = window.matchMedia?.("(prefers-color-scheme: dark)") ?? null;
      if (!this.mediaQuery) {
        return;
      }

      const handler = (event: MediaQueryListEvent) => {
        const mode: ThemeMode = event.matches ? "dark" : "light";
        this.modeSignal.set(mode);
        this.applyThemeClass(mode);
      };

      if (typeof this.mediaQuery.addEventListener === "function") {
        this.mediaQuery.addEventListener("change", handler);
      } else if (typeof this.mediaQuery.addListener === "function") {
        this.mediaQuery.addListener(handler);
      }
    } catch {
      // Ignore unsupported environments.
    }
  }

  private applyThemeClass(mode: ThemeMode): void {
    const root = this.document.documentElement;
    const body = this.document.body;
    root.classList.toggle("dark-theme", mode === "dark");
    root.setAttribute("data-theme", mode);
    body.classList.toggle("dark-theme", mode === "dark");
    body.setAttribute("data-theme", mode);
  }
}
