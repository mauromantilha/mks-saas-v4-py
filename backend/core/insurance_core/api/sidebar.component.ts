import { Component } from '@angular/core';

@Component({
  selector: 'app-sidebar',
  template: `
    <div class="logo-container">
      <span class="logo-text">MKS Enterprise</span>
    </div>
    <mat-nav-list>
      <a mat-list-item routerLink="/policies" routerLinkActive="active-link">
        <mat-icon matListItemIcon>policy</mat-icon>
        <span matListItemTitle>Apólices</span>
      </a>
      <a mat-list-item routerLink="/finance" routerLinkActive="active-link">
        <mat-icon matListItemIcon>attach_money</mat-icon>
        <span matListItemTitle>Financeiro</span>
      </a>
      <a mat-list-item routerLink="/commission" routerLinkActive="active-link">
        <mat-icon matListItemIcon>payments</mat-icon>
        <span matListItemTitle>Comissões</span>
      </a>
      <a mat-list-item routerLink="/claims" routerLinkActive="active-link">
        <mat-icon matListItemIcon>warning</mat-icon>
        <span matListItemTitle>Sinistros</span>
      </a>
      <a mat-list-item routerLink="/documents" routerLinkActive="active-link">
        <mat-icon matListItemIcon>folder</mat-icon>
        <span matListItemTitle>Documentos</span>
      </a>
    </mat-nav-list>
  `,
  styles: [`
    .logo-container { height: 64px; display: flex; align-items: center; padding: 0 16px; border-bottom: 1px solid rgba(0,0,0,0.12); }
    .logo-text { font-weight: 500; font-size: 20px; color: #3f51b5; }
    .active-link { background-color: rgba(63, 81, 181, 0.1); color: #3f51b5; }
    mat-icon { margin-right: 10px; }
  `]
})
export class SidebarComponent {}