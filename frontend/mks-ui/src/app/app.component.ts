import { CommonModule } from "@angular/common";
import { Component } from "@angular/core";
import { Router, RouterLink, RouterOutlet } from "@angular/router";

import { SessionService } from "./core/auth/session.service";

@Component({
  selector: "app-root",
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink],
  templateUrl: "./app.component.html",
  styleUrl: "./app.component.scss",
})
export class AppComponent {
  constructor(
    public readonly sessionService: SessionService,
    private readonly router: Router
  ) {}

  logout(): void {
    this.sessionService.clearSession();
    void this.router.navigate(["/login"]);
  }
}
