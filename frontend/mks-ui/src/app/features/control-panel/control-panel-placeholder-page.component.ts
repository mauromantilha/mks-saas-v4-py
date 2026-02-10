import { CommonModule } from "@angular/common";
import { Component, computed } from "@angular/core";
import { ActivatedRoute } from "@angular/router";

@Component({
  selector: "app-control-panel-placeholder-page",
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="placeholder">
      <h1>{{ title() }}</h1>
      <p>{{ description() }}</p>
      <small>Placeholder inicial do módulo control-panel.</small>
    </section>
  `,
  styles: `
    .placeholder {
      border: 1px solid var(--mks-border);
      background: var(--mks-surface);
      border-radius: 14px;
      padding: 20px;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 1.2rem;
    }

    p {
      margin: 0 0 8px;
    }
  `,
})
export class ControlPanelPlaceholderPageComponent {
  readonly title = computed(
    () => (this.route.snapshot.data["title"] as string | undefined) ?? "Control Panel"
  );
  readonly description = computed(
    () =>
      (this.route.snapshot.data["description"] as string | undefined) ??
      "Página inicial em construção."
  );

  constructor(private readonly route: ActivatedRoute) {}
}
