import { Injectable, signal } from "@angular/core";
import { ActivatedRoute } from "@angular/router";

@Injectable({ providedIn: "root" })
export class BreadcrumbService {
  readonly breadcrumbs = signal<string[]>([]);

  buildFromRoute(rootRoute: ActivatedRoute | null | undefined, rootLabel = "Control Panel"): void {
    const crumbs = [rootLabel];
    if (!rootRoute) {
      this.breadcrumbs.set(crumbs);
      return;
    }

    let route: ActivatedRoute | null | undefined = rootRoute.firstChild;
    let guard = 0;
    while (route && guard < 25) {
      const title = route.snapshot?.data?.["title"] as string | undefined;
      if (title) {
        crumbs.push(title);
      }
      route = route.firstChild;
      guard += 1;
    }

    this.breadcrumbs.set(crumbs);
  }
}
