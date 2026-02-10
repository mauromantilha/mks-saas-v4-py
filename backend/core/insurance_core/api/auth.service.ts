import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { catchError, tap } from 'rxjs/operators';

export interface User {
  id: number;
  username: string;
  email: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly API_URL = '/api';
  private readonly TOKEN_KEY = 'auth_token';

  private isAuthenticatedSubject = new BehaviorSubject<boolean>(this.hasToken());
  public isAuthenticated$ = this.isAuthenticatedSubject.asObservable();

  private userPermissionsSubject = new BehaviorSubject<string[]>([]);
  public userPermissions$ = this.userPermissionsSubject.asObservable();

  private currentUserSubject = new BehaviorSubject<User | null>(null);
  public currentUser$ = this.currentUserSubject.asObservable();

  constructor(private http: HttpClient, private router: Router) {
    if (this.hasToken()) {
      this.loadUserProfile();
      this.loadPermissions();
    }
  }

  login(credentials: { username: string; password: string }): Observable<any> {
    return this.http.post<{ token: string }>(`${this.API_URL}/auth/token/`, credentials).pipe(
      tap(response => {
        this.setToken(response.token);
        this.isAuthenticatedSubject.next(true);
        this.loadUserProfile();
        this.loadPermissions();
      })
    );
  }

  logout(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    this.isAuthenticatedSubject.next(false);
    this.userPermissionsSubject.next([]);
    this.currentUserSubject.next(null);
    this.router.navigate(['/login']);
  }

  refreshToken(): Observable<any> {
    // Placeholder para refresh token se suportado pelo backend
    return of(null);
  }

  getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  private setToken(token: string): void {
    localStorage.setItem(this.TOKEN_KEY, token);
  }

  private hasToken(): boolean {
    return !!this.getToken();
  }

  private loadUserProfile(): void {
    this.http.get<User>(`${this.API_URL}/users/me/`).pipe(
      catchError(() => of(null))
    ).subscribe(user => this.currentUserSubject.next(user));
  }

  private loadPermissions(): void {
    // Mapeia a resposta do TenantCapabilitiesAPIView para uma lista de strings 'resource.verb'
    this.http.get<any>(`${this.API_URL}/tenants/capabilities/`).pipe(
      catchError(() => of({ capabilities: {} }))
    ).subscribe(response => {
      const perms: string[] = [];
      if (response.capabilities) {
        for (const [resource, actions] of Object.entries(response.capabilities)) {
          for (const [action, allowed] of Object.entries(actions as any)) {
            if (allowed) {
              perms.push(`${resource}.${action}`);
            }
          }
        }
      }
      this.userPermissionsSubject.next(perms);
    });
  }
}