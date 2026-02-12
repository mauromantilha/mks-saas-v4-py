import { CommonModule, DatePipe } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";

import { LedgerService } from "../../core/api/ledger.service";
import { LedgerEntry } from "../../core/api/ledger.types";

@Component({
  selector: "app-tenant-ledger-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule, DatePipe],
  templateUrl: "./tenant-ledger-page.component.html",
  styleUrl: "./tenant-ledger-page.component.scss",
})
export class TenantLedgerPageComponent {
  loading = signal(false);
  error = signal("");
  entries = signal<LedgerEntry[]>([]);
  limit = signal(200);

  constructor(private readonly ledgerService: LedgerService) {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");
    this.ledgerService.list(this.limit()).subscribe({
      next: (data) => {
        this.entries.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar ledger do tenant."
        );
        this.loading.set(false);
      },
    });
  }
}

