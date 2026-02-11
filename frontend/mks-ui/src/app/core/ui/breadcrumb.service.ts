import { Injectable, signal } from "@angular/core";
import { ActivatedRoute } from "@angular/router";

@Injectable({ providedIn: "root" })
export class BreadcrumbService {
  readonly breadcrumbs = signal<string[]>([]);

  buildFromRoute(rootRoute: ActivatedRoute, rootLabel = "Control Panel"): void {
    const crumbs = [rootLabel];
    let route: ActivatedRoute | null = rootRoute.firstChild;

    while (route) {
      const title = route.snapshot.data["title"] as string | undefined;
      if (title) {
        crumbs.push(title);
      }
      route = route.firstChild;
    }

    this.breadcrumbs.set(crumbs);
  }
}

