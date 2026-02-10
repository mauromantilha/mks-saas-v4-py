import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router } from '@angular/router';
import { filter, distinctUntilChanged } from 'rxjs/operators';

export interface Breadcrumb {
  label: string;
  url: string;
}

@Component({
  selector: 'app-breadcrumbs',
  template: `
    <div class="breadcrumbs-container">
      <ng-container *ngFor="let breadcrumb of breadcrumbs; let last = last">
        <a [routerLink]="breadcrumb.url" class="breadcrumb-link">{{ breadcrumb.label }}</a>
        <mat-icon *ngIf="!last" class="separator">chevron_right</mat-icon>
      </ng-container>
    </div>
  `,
  styles: [`
    .breadcrumbs-container { display: flex; align-items: center; font-size: 14px; color: #666; }
    .breadcrumb-link { text-decoration: none; color: inherit; }
    .breadcrumb-link:hover { text-decoration: underline; color: #3f51b5; }
    .separator { font-size: 16px; height: 16px; width: 16px; margin: 0 4px; display: flex; align-items: center; }
  `]
})
export class BreadcrumbsComponent implements OnInit {
  breadcrumbs: Breadcrumb[] = [];

  constructor(private router: Router, private activatedRoute: ActivatedRoute) {}

  ngOnInit() {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd),
      distinctUntilChanged(),
    ).subscribe(() => {
      this.breadcrumbs = this.buildBreadCrumb(this.activatedRoute.root);
    });
  }

  buildBreadCrumb(route: ActivatedRoute, url: string = '', breadcrumbs: Breadcrumb[] = []): Breadcrumb[] {
    const label = route.routeConfig && route.routeConfig.data ? route.routeConfig.data['breadcrumb'] : '';
    let path = route.routeConfig ? route.routeConfig.path : '';

    const lastRoutePart = path!.split('/').pop();
    const isDynamicRoute = lastRoutePart!.startsWith(':');
    if (isDynamicRoute && !!route.snapshot) {
      const paramName = lastRoutePart!.split(':')[1];
      path = path!.replace(lastRoutePart!, route.snapshot.params[paramName]);
    }

    const nextUrl = path ? `${url}/${path}` : url;
    const breadcrumb: Breadcrumb = { label: label, url: nextUrl };
    const newBreadcrumbs = breadcrumb.label ? [...breadcrumbs, breadcrumb] : [...breadcrumbs];
    
    if (route.firstChild) return this.buildBreadCrumb(route.firstChild, nextUrl, newBreadcrumbs);
    return newBreadcrumbs;
  }
}