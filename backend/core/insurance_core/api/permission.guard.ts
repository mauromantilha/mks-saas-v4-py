import { Injectable } from '@angular/core';
import { CanActivate, ActivatedRouteSnapshot, Router, UrlTree } from '@angular/router';
import { Observable } from 'rxjs';
import { map, take } from 'rxjs/operators';
import { PermissionService } from './permission.service';

@Injectable({
  providedIn: 'root'
})
export class PermissionGuard implements CanActivate {
  constructor(private permissionService: PermissionService, private router: Router) {}

  canActivate(route: ActivatedRouteSnapshot): Observable<boolean | UrlTree> {
    const requiredPermission = route.data['permission'];
    
    if (!requiredPermission) {
      return new Observable(obs => obs.next(true));
    }

    return this.permissionService.can(requiredPermission).pipe(
      take(1),
      map(permissions => {
        return permissions 
          ? true 
          : this.router.parseUrl('/403');
      })
    );
  }
}