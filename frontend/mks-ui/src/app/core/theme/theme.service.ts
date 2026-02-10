import { DOCUMENT } from "@angular/common";
import { Inject, Injectable, computed, signal } from "@angular/core";

type ThemeMode = "light" | "dark";

@Injectable({ providedIn: "root" })
export class ThemeService {
  private readonly storageKey = "mks_ui_theme_mode";
  private readonly modeSignal = signal<ThemeMode>("light");

  readonly mode = computed(() => this.modeSignal());
  readonly isDarkMode = computed(() => this.modeSignal() === "dark");

  constructor(@Inject(DOCUMENT) private readonly document: Document) {
    this.initialize();
  }

  setDarkMode(enabled: boolean): void {
    const mode: ThemeMode = enabled ? "dark" : "light";
    this.modeSignal.set(mode);
    this.applyThemeClass(mode);
    this.persistMode(mode);
  }

  toggle(): void {
    this.setDarkMode(!this.isDarkMode());
  }

  private initialize(): void {
    const stored = this.readStoredMode();
    const prefersDark = this.prefersDarkMode();
    const mode = stored ?? (prefersDark ? "dark" : "light");
    this.modeSignal.set(mode);
    this.applyThemeClass(mode);
  }

  private readStoredMode(): ThemeMode | null {
    try {
      const raw = window.localStorage.getItem(this.storageKey);
      if (raw === "dark" || raw === "light") {
        return raw;
      }
      return null;
    } catch {
      return null;
    }
  }

  private persistMode(mode: ThemeMode): void {
    try {
      window.localStorage.setItem(this.storageKey, mode);
    } catch {
      // Best effort only.
    }
  }

  private prefersDarkMode(): boolean {
    try {
      return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? false;
    } catch {
      return false;
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
