import { CommonModule, DatePipe } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { FinanceFiscalService } from "../../core/api/finance-fiscal.service";
import {
  FiscalDocumentRecord,
  FiscalDocumentStatus,
  FiscalEnvironment,
  TenantFiscalConfigRecord,
} from "../../core/api/finance-fiscal.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-fiscal-page",
  standalone: true,
  imports: [CommonModule, FormsModule, DatePipe],
  templateUrl: "./tenant-fiscal-page.component.html",
  styleUrl: "./tenant-fiscal-page.component.scss",
})
export class TenantFiscalPageComponent {
  private readonly brlFormatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  // Config.
  configLoading = signal(false);
  configError = signal("");
  configNotice = signal("");
  config = signal<TenantFiscalConfigRecord | null>(null);

  provider = signal("mock");
  environment = signal<FiscalEnvironment>("SANDBOX");
  autoIssue = signal(false);
  token = signal("");
  tokenVisible = signal(false);

  // Documents.
  docsLoading = signal(false);
  docsError = signal("");
  docsNotice = signal("");
  documents = signal<FiscalDocumentRecord[]>([]);

  statusFilter = signal<FiscalDocumentStatus | "">("");
  invoiceFilter = signal("");
  search = signal("");

  // Issue.
  issueInvoiceId = signal("");
  issueError = signal("");

  readonly environments: { label: string; value: FiscalEnvironment }[] = [
    { label: "Sandbox", value: "SANDBOX" },
    { label: "Production", value: "PRODUCTION" },
  ];

  constructor(
    private readonly financeFiscalService: FinanceFiscalService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.loadConfig();
    this.loadDocuments();
  }

  loadConfig(): void {
    this.configLoading.set(true);
    this.configError.set("");
    this.configNotice.set("");

    this.financeFiscalService.getActiveConfig().subscribe({
      next: (resp) => {
        this.config.set(resp);
        this.provider.set(resp.provider_type || "mock");
        this.environment.set(resp.environment);
        this.autoIssue.set(Boolean(resp.auto_issue));
        this.token.set("");
        this.configLoading.set(false);
      },
      error: (err) => {
        if (err?.status === 404) {
          this.config.set(null);
          this.configNotice.set("Nenhuma configuração fiscal ativa encontrada. Cadastre abaixo.");
          this.configLoading.set(false);
          return;
        }
        this.configError.set(
          err?.error?.detail ? String(err.error.detail) : "Erro ao carregar configuração fiscal."
        );
        this.configLoading.set(false);
      },
    });
  }

  saveConfig(): void {
    if (!this.canWrite()) {
      this.configError.set("Seu perfil é somente leitura.");
      return;
    }

    const provider = this.provider().trim();
    if (!provider) {
      this.configError.set("Informe o provider (ex: mock, focusnfe, nfeio).");
      return;
    }

    this.configLoading.set(true);
    this.configError.set("");
    this.configNotice.set("");

    const payload = {
      provider,
      environment: this.environment(),
      auto_issue: Boolean(this.autoIssue()),
      token: this.token().trim() || undefined,
    };

    this.financeFiscalService.upsertConfig(payload).subscribe({
      next: (resp) => {
        this.config.set(resp);
        this.token.set("");
        this.configNotice.set("Configuração fiscal salva com sucesso.");
        this.configLoading.set(false);
      },
      error: (err) => {
        this.configError.set(
          err?.error?.detail ? String(err.error.detail) : "Erro ao salvar configuração fiscal."
        );
        this.configLoading.set(false);
      },
    });
  }

  loadDocuments(): void {
    this.docsLoading.set(true);
    this.docsError.set("");
    this.docsNotice.set("");

    this.financeFiscalService
      .listDocuments({
        status: this.statusFilter(),
        invoice_id: this.invoiceFilter(),
        q: this.search(),
      })
      .subscribe({
        next: (resp) => {
          this.documents.set(resp);
          this.docsLoading.set(false);
        },
        error: (err) => {
          this.docsError.set(
            err?.error?.detail ? String(err.error.detail) : "Erro ao carregar documentos fiscais."
          );
          this.docsLoading.set(false);
        },
      });
  }

  issue(): void {
    if (!this.canWrite()) {
      this.issueError.set("Seu perfil é somente leitura.");
      return;
    }
    const raw = this.issueInvoiceId().trim();
    const invoiceId = Number.parseInt(raw, 10);
    if (!raw || Number.isNaN(invoiceId) || invoiceId <= 0) {
      this.issueError.set("Informe um invoice_id válido (> 0).");
      return;
    }

    this.docsLoading.set(true);
    this.docsError.set("");
    this.docsNotice.set("");
    this.issueError.set("");

    this.financeFiscalService.issue(invoiceId).subscribe({
      next: () => {
        this.docsNotice.set("NF emitida (ou enviada para emissão) com sucesso.");
        this.issueInvoiceId.set("");
        this.loadDocuments();
      },
      error: (err) => {
        this.issueError.set(
          err?.error?.detail ? String(err.error.detail) : "Erro ao emitir NF."
        );
        this.docsLoading.set(false);
      },
    });
  }

  cancel(doc: FiscalDocumentRecord): void {
    if (!this.canWrite()) {
      this.docsError.set("Seu perfil é somente leitura.");
      return;
    }
    if (doc.status === "CANCELLED") {
      return;
    }
    const ok = window.confirm(
      `Cancelar NF ${doc.series || "-"}-${doc.number || "-"} (documento ${doc.id})?`
    );
    if (!ok) {
      return;
    }

    this.docsLoading.set(true);
    this.docsError.set("");
    this.docsNotice.set("");

    this.financeFiscalService.cancel(doc.id).subscribe({
      next: (resp) => {
        const next = this.documents().map((row) => (row.id === resp.id ? resp : row));
        this.documents.set(next);
        this.docsNotice.set("Documento fiscal cancelado.");
        this.docsLoading.set(false);
      },
      error: (err) => {
        this.docsError.set(
          err?.error?.detail ? String(err.error.detail) : "Erro ao cancelar documento fiscal."
        );
        this.docsLoading.set(false);
      },
    });
  }

  retry(doc: FiscalDocumentRecord): void {
    if (!this.canWrite()) {
      this.docsError.set("Seu perfil é somente leitura.");
      return;
    }
    this.docsLoading.set(true);
    this.docsError.set("");
    this.docsNotice.set("");

    this.financeFiscalService.retry(doc.id).subscribe({
      next: (resp) => {
        this.docsNotice.set(
          `Reprocessamento agendado. job_id=${resp.job_id} attempts=${resp.attempts}`
        );
        this.loadDocuments();
      },
      error: (err) => {
        this.docsError.set(
          err?.error?.detail ? String(err.error.detail) : "Erro ao reprocessar documento fiscal."
        );
        this.docsLoading.set(false);
      },
    });
  }

  formatCurrency(value: string | number | null | undefined): string {
    const resolved =
      typeof value === "number" ? value : Number.parseFloat(String(value ?? "0"));
    return this.brlFormatter.format(Number.isFinite(resolved) ? resolved : 0);
  }

  jobStatusLabel(doc: FiscalDocumentRecord): string {
    if (!doc.job) {
      return "-";
    }
    return doc.job.status;
  }

  canRetry(doc: FiscalDocumentRecord): boolean {
    return Boolean(doc.job && doc.job.status === "FAILED");
  }
}

