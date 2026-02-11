import { Directive, Input, TemplateRef, ViewContainerRef } from "@angular/core";

import { PermissionService } from "./permission.service";

@Directive({
  selector: "[appCan]",
  standalone: true,
})
export class PermissionDirective {
  private currentPermission = "";

  constructor(
    private readonly templateRef: TemplateRef<unknown>,
    private readonly viewContainer: ViewContainerRef,
    private readonly permissionService: PermissionService
  ) {}

  @Input()
  set appCan(permission: string) {
    this.currentPermission = permission;
    this.permissionService.loadPermissions();
    this.updateView();
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

