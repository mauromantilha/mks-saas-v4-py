import { Component } from '@angular/core';

@Component({
  selector: 'app-layout',
  template: `
    <mat-sidenav-container class="app-container">
      <mat-sidenav mode="side" opened class="app-sidebar">
        <app-sidebar></app-sidebar>
      </mat-sidenav>
      <mat-sidenav-content class="main-content">
        <app-topbar></app-topbar>
        <div class="content-wrapper">
          <router-outlet></router-outlet>
        </div>
      </mat-sidenav-content>
    </mat-sidenav-container>
  `,
  styles: [`
    .app-container { height: 100vh; }
    .app-sidebar { width: 250px; border-right: 1px solid rgba(0,0,0,0.12); }
    .main-content { display: flex; flex-direction: column; height: 100%; }
    .content-wrapper { flex: 1; overflow: auto; padding: 20px; }
  `]
})
export class LayoutComponent {}