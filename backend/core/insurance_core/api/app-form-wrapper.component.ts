import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-form-wrapper',
  template: `
    <div class="form-wrapper mat-elevation-z2">
      <div class="header" *ngIf="title">
        <h2 class="title">{{ title }}</h2>
        <div class="header-actions">
          <ng-content select="[header-actions]"></ng-content>
        </div>
      </div>

      <div class="content">
        <ng-content></ng-content>
      </div>

      <div class="footer">
        <ng-content select="[footer-actions]"></ng-content>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; }
    .form-wrapper { background: white; border-radius: 4px; overflow: hidden; }
    .header { padding: 16px 24px; border-bottom: 1px solid rgba(0,0,0,0.12); display: flex; justify-content: space-between; align-items: center; }
    .title { margin: 0; font-size: 1.25rem; font-weight: 500; color: rgba(0,0,0,0.87); }
    .content { padding: 24px; }
    .footer { padding: 16px 24px; background: #fafafa; border-top: 1px solid rgba(0,0,0,0.12); display: flex; justify-content: flex-end; gap: 10px; }
    .footer:empty { display: none; }
  `]
})
export class AppFormWrapperComponent {
  @Input() title: string = '';
}