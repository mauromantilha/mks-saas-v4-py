import { DOCUMENT } from "@angular/common";
import { Inject, Injectable, computed, signal } from "@angular/core";

type ThemeMode = "light" | "dark";

@Injectable({ providedIn: "root" })
export class ThemeService {
  private readonly modeSignal = signal<ThemeMode>("light");

  readonly mode = computed(() => this.modeSignal());
  readonly isDarkMode = computed(() => this.modeSignal() === "dark");

  constructor(@Inject(DOCUMENT) private readonly document: Document) {
    this.initialize();
  }

  setDarkMode(_enabled: boolean): void {
    // Project decision: keep UI in light mode until final stabilization.
    const mode: ThemeMode = "light";
    this.modeSignal.set(mode);
    this.applyThemeClass(mode);
  }

  toggle(): void {
    this.setDarkMode(false);
  }

  private initialize(): void {
    const mode: ThemeMode = "light";
    this.modeSignal.set(mode);
    this.applyThemeClass(mode);
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
