import { Component } from '@angular/core';
import { Observable } from 'rxjs';
import { AuthService } from './core/auth/auth.service';
import { ThemeService } from './core/services/theme.service';

@Component({
  selector: 'app-topbar',
  template: `
    <mat-toolbar class="topbar">
      <app-breadcrumbs></app-breadcrumbs>
      <span class="spacer"></span>
      
      <button mat-icon-button (click)="toggleTheme()" title="Alternar Tema">
        <mat-icon>{{ (isDark$ | async) ? 'light_mode' : 'dark_mode' }}</mat-icon>
      </button>

      <button mat-icon-button [matMenuTriggerFor]="menu">
        <mat-icon>account_circle</mat-icon>
      </button>
      <mat-menu #menu="matMenu">
        <button mat-menu-item>
          <mat-icon>person</mat-icon>
          <span>Perfil</span>
        </button>
        <button mat-menu-item (click)="logout()">
          <mat-icon>exit_to_app</mat-icon>
          <span>Sair</span>
        </button>
      </mat-menu>
    </mat-toolbar>
  `,
  styles: [`
    .topbar { background: white; color: #333; }
    .spacer { flex: 1 1 auto; }
  `]
})
export class TopbarComponent {
  isDark$: Observable<boolean>;

  constructor(
    private authService: AuthService,
    private themeService: ThemeService
  ) {
    this.isDark$ = this.themeService.isDark$;
  }
  toggleTheme() { this.themeService.toggle(); }
  logout() { this.authService.logout(); }
}