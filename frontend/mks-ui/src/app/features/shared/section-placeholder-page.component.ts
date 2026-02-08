import { CommonModule } from "@angular/common";
import { Component, computed } from "@angular/core";
import { ActivatedRoute } from "@angular/router";

@Component({
  selector: "app-section-placeholder-page",
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="placeholder-wrap">
      <h1>{{ title() }}</h1>
      <p>{{ description() }}</p>
      <p class="muted">
        Este menu já está reservado no portal e será evoluído nos próximos módulos.
      </p>
    </section>
  `,
  styles: `
    .placeholder-wrap {
      max-width: 920px;
      margin: 20px auto;
      padding: 0 16px;
    }
    h1 {
      margin: 0 0 8px;
    }
    p {
      margin: 0 0 12px;
    }
    .muted {
      color: #667085;
      font-size: 0.95rem;
    }
  `,
})
export class SectionPlaceholderPageComponent {
  readonly title = computed(
    () => (this.route.snapshot.data["title"] as string | undefined) ?? "Módulo"
  );
  readonly description = computed(
    () =>
      (this.route.snapshot.data["description"] as string | undefined) ??
      "Área inicial em construção."
  );

  constructor(private readonly route: ActivatedRoute) {}
}
