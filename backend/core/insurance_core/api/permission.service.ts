import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { AuthService } from './auth.service';

@Injectable({
  providedIn: 'root'
})
export class PermissionService {
  constructor(private authService: AuthService) {}

  can(permission: string): Observable<boolean> {
    return this.authService.userPermissions$.pipe(
      map(permissions => permissions.includes(permission))
    );
  }
}