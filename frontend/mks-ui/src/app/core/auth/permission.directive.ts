import { Directive, Input, OnDestroy, TemplateRef, ViewContainerRef, effect } from "@angular/core";
import { Subscription } from "rxjs";
import { take } from "rxjs/operators";

import { PermissionService } from "./permission.service";

@Directive({
  selector: "[appCan]",
  standalone: true,
})
export class PermissionDirective implements OnDestroy {
  private currentPermission = "";
  private loadSubscription: Subscription | null = null;

  constructor(
    private readonly templateRef: TemplateRef<unknown>,
    private readonly viewContainer: ViewContainerRef,
    private readonly permissionService: PermissionService
  ) {
    effect(() => {
      this.permissionService.version();
      this.updateView();
    });
  }

  @Input()
  set appCan(permission: string) {
    this.currentPermission = permission;
    this.loadSubscription?.unsubscribe();
    this.loadSubscription = this.permissionService
      .loadPermissions()
      .pipe(take(1))
      .subscribe({
        next: () => this.updateView(),
        error: () => this.updateView(),
      });
    this.updateView();
  }

  ngOnDestroy(): void {
    this.loadSubscription?.unsubscribe();
  }

  private updateView(): void {
    if (!this.currentPermission) {
      this.viewContainer.clear();
      return;
    }

    if (this.permissionService.can(this.currentPermission)) {
      if (this.viewContainer.length === 0) {
        this.viewContainer.createEmbeddedView(this.templateRef);
      }
      return;
    }

    this.viewContainer.clear();
  }
}
