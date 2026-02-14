import { CommonModule } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  CustomerRecord,
  SpecialProjectActivityRecord,
  SpecialProjectDocumentRecord,
  SpecialProjectRecord,
} from "../../core/api/sales-flow.types";
import { TenantMembersService } from "../../core/api/tenant-members.service";
import { TenantMember } from "../../core/api/tenant-members.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-special-projects-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule],
  templateUrl: "./tenant-special-projects-page.component.html",
  styleUrl: "./tenant-special-projects-page.component.scss",
})
export class TenantSpecialProjectsPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");

  customers = signal<CustomerRecord[]>([]);
  members = signal<TenantMember[]>([]);
  projects = signal<SpecialProjectRecord[]>([]);
  selectedProject = signal<SpecialProjectRecord | null>(null);

  statusFilter = signal("");
  projectAction = signal("CRIAR");

  useExistingCustomer = signal(true);
  customerId = signal<number | null>(null);
  newCustomerName = signal("");
  newCustomerDocument = signal("");
  newCustomerPhone = signal("");
  newCustomerEmail = signal("");

  projectName = signal("");
  projectType = signal<"TRANSFER_RISK" | "RISK_MANAGEMENT">("TRANSFER_RISK");
  ownerId = signal<number | null>(null);
  startDate = signal("");
  dueDate = signal("");
  swotStrengths = signal("");
  swotWeaknesses = signal("");
  swotOpportunities = signal("");
  swotThreats = signal("");
  notes = signal("");

  activityTitle = signal("");
  activityDescription = signal("");
  activityDueDate = signal("");

  lossReason = signal("");

  readonly projectTypeOptions = [
    { label: "Transferência de Risco (Seguros)", value: "TRANSFER_RISK" as const },
    { label: "Gestão de Riscos", value: "RISK_MANAGEMENT" as const },
  ];

  readonly statusFilterOptions = [
    { label: "Todos", value: "" },
    { label: "Aberto", value: "OPEN" },
    { label: "Fechado", value: "CLOSED" },
    { label: "Ganho", value: "CLOSED_WON" },
    { label: "Perdido", value: "CLOSED_LOST" },
  ];

  readonly actionOptions = [
    { label: "Criar", value: "CRIAR" },
    { label: "Atualizar", value: "ATUALIZAR" },
    { label: "Encerrar", value: "ENCERRAR" },
  ];

  readonly customerSelectOptions = computed(() =>
    this.customers().map((c) => ({
      label: `#${c.id} - ${c.name}`,
      value: c.id,
    }))
  );

  readonly memberOwnerOptions = computed(() =>
    this.members().map((m) => ({
      label: `${m.username} (${m.role})`,
      value: m.user_id,
    }))
  );

  readonly memberSimpleOptions = computed(() =>
    this.members().map((m) => ({
      label: m.username,
      value: m.user_id,
    }))
  );

  constructor(
    private readonly salesFlowService: SalesFlowService,
    private readonly tenantMembersService: TenantMembersService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.bootstrap();
  }

  private parseError(err: unknown, fallback: string): string {
    const e = err as { error?: { detail?: unknown; [key: string]: unknown } };
    if (typeof e?.error?.detail === "string") {
      return e.error.detail;
    }
    if (e?.error && typeof e.error === "object") {
      const parts: string[] = [];
      Object.entries(e.error).forEach(([k, v]) => {
        if (Array.isArray(v)) {
          parts.push(`${k}: ${v.join(" ")}`);
        } else if (typeof v === "string") {
          parts.push(`${k}: ${v}`);
        }
      });
      if (parts.length > 0) {
        return parts.join(" | ");
      }
    }
    return fallback;
  }

  bootstrap(): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    let done = 0;
    const finish = () => {
      done += 1;
      if (done >= 3) {
        this.loading.set(false);
      }
    };

    this.salesFlowService.listCustomers().subscribe({
      next: (rows) => {
        this.customers.set(rows);
        finish();
      },
      error: (err) => {
        this.error.set(this.parseError(err, "Erro ao carregar clientes."));
        this.loading.set(false);
      },
    });

    this.tenantMembersService.list().subscribe({
      next: (resp) => {
        this.members.set(resp.results);
        finish();
      },
      error: () => {
        this.members.set([]);
        finish();
      },
    });

    this.loadProjects();
  }

  loadProjects(): void {
    this.loading.set(true);
    this.salesFlowService
      .listSpecialProjects({ status: this.statusFilter() || undefined })
      .subscribe({
        next: (rows) => {
          this.projects.set(rows);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao carregar projetos especiais."));
          this.loading.set(false);
        },
      });
  }

  changeCustomerMode(useExisting: boolean): void {
    this.useExistingCustomer.set(useExisting);
    if (useExisting) {
      this.newCustomerName.set("");
      this.newCustomerDocument.set("");
      this.newCustomerPhone.set("");
      this.newCustomerEmail.set("");
    } else {
      this.customerId.set(null);
    }
  }

  createProject(): void {
    if (!this.canWrite()) {
      return;
    }
    if (!this.projectName().trim()) {
      this.error.set("Nome do projeto é obrigatório.");
      return;
    }
    if (!this.startDate() || !this.dueDate()) {
      this.error.set("Data de início e data de entrega são obrigatórias.");
      return;
    }

    const payload: Record<string, unknown> = {
      name: this.projectName().trim(),
      project_type: this.projectType(),
      owner: this.ownerId(),
      start_date: this.startDate(),
      due_date: this.dueDate(),
      swot_strengths: this.swotStrengths().trim(),
      swot_weaknesses: this.swotWeaknesses().trim(),
      swot_opportunities: this.swotOpportunities().trim(),
      swot_threats: this.swotThreats().trim(),
      notes: this.notes().trim(),
    };

    if (this.useExistingCustomer()) {
      payload["customer"] = this.customerId();
      if (!this.customerId()) {
        this.error.set("Selecione um cliente ou cadastre novo para o projeto.");
        return;
      }
    } else {
      if (!this.newCustomerName().trim() || !this.newCustomerDocument().trim() || !this.newCustomerEmail().trim()) {
        this.error.set("No cadastro simplificado, informe nome, CPF/CNPJ e email.");
        return;
      }
      payload["prospect_name"] = this.newCustomerName().trim();
      payload["prospect_document"] = this.newCustomerDocument().trim();
      payload["prospect_phone"] = this.newCustomerPhone().trim();
      payload["prospect_email"] = this.newCustomerEmail().trim();
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.createSpecialProject(payload as any).subscribe({
      next: (row) => {
        this.notice.set(`Projeto #${row.id} criado.`);
        this.resetCreateForm();
        this.projects.set([row, ...this.projects()]);
        this.openProject(row.id);
      },
      error: (err) => {
        this.error.set(this.parseError(err, "Erro ao criar projeto."));
        this.loading.set(false);
      },
    });
  }

  resetCreateForm(): void {
    this.useExistingCustomer.set(true);
    this.customerId.set(null);
    this.newCustomerName.set("");
    this.newCustomerDocument.set("");
    this.newCustomerPhone.set("");
    this.newCustomerEmail.set("");
    this.projectName.set("");
    this.projectType.set("TRANSFER_RISK");
    this.ownerId.set(null);
    this.startDate.set("");
    this.dueDate.set("");
    this.swotStrengths.set("");
    this.swotWeaknesses.set("");
    this.swotOpportunities.set("");
    this.swotThreats.set("");
    this.notes.set("");
  }

  openProject(id: number): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.getSpecialProject(id).subscribe({
      next: (row) => {
        this.selectedProject.set(row);
        this.lossReason.set(row.loss_reason || "");
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.parseError(err, "Erro ao abrir projeto."));
        this.loading.set(false);
      },
    });
  }

  closeProject(): void {
    this.selectedProject.set(null);
    this.activityTitle.set("");
    this.activityDescription.set("");
    this.activityDueDate.set("");
    this.lossReason.set("");
  }

  updateProjectStatus(status: "CLOSED" | "CLOSED_WON" | "CLOSED_LOST"): void {
    const project = this.selectedProject();
    if (!project || !this.canWrite()) {
      return;
    }
    const payload: Record<string, unknown> = { status };
    if (status === "CLOSED_LOST") {
      if (!this.lossReason().trim()) {
        this.error.set("Informe o motivo da perda.");
        return;
      }
      payload["loss_reason"] = this.lossReason().trim();
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.updateSpecialProject(project.id, payload as any).subscribe({
      next: (row) => {
        this.notice.set(`Projeto #${row.id} atualizado para ${row.status}.`);
        this.selectedProject.set(row);
        this.refreshProjectInList(row);
        if (row.status === "CLOSED_WON") {
          this.notice.set(
            `Projeto #${row.id} marcado como ganho e cliente convertido automaticamente.`
          );
        }
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.parseError(err, "Erro ao alterar status do projeto."));
        this.loading.set(false);
      },
    });
  }

  saveProjectChanges(project: SpecialProjectRecord): void {
    if (!this.canWrite()) {
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .updateSpecialProject(project.id, {
        name: project.name,
        project_type: project.project_type,
        owner: project.owner,
        start_date: project.start_date,
        due_date: project.due_date,
        swot_strengths: project.swot_strengths,
        swot_weaknesses: project.swot_weaknesses,
        swot_opportunities: project.swot_opportunities,
        swot_threats: project.swot_threats,
        notes: project.notes,
      })
      .subscribe({
        next: (row) => {
          this.notice.set(`Projeto #${row.id} salvo.`);
          this.selectedProject.set(row);
          this.refreshProjectInList(row);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao salvar alterações do projeto."));
          this.loading.set(false);
        },
      });
  }

  deleteProject(project: SpecialProjectRecord): void {
    if (!this.canWrite()) {
      return;
    }
    if (!window.confirm(`Excluir projeto #${project.id}?`)) {
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.deleteSpecialProject(project.id).subscribe({
      next: () => {
        this.notice.set(`Projeto #${project.id} excluído.`);
        this.projects.set(this.projects().filter((row) => row.id !== project.id));
        if (this.selectedProject()?.id === project.id) {
          this.closeProject();
        }
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.parseError(err, "Erro ao excluir projeto."));
        this.loading.set(false);
      },
    });
  }

  addActivity(): void {
    const project = this.selectedProject();
    if (!project || !this.canWrite()) {
      return;
    }
    if (!this.activityTitle().trim()) {
      this.error.set("Título da atividade é obrigatório.");
      return;
    }

    this.loading.set(true);
    this.error.set("");

    this.salesFlowService
      .addSpecialProjectActivity(project.id, {
        title: this.activityTitle().trim(),
        description: this.activityDescription().trim(),
        due_date: this.activityDueDate() || null,
      })
      .subscribe({
        next: (activity) => {
          const current = this.selectedProject();
          if (!current) {
            return;
          }
          this.selectedProject.set({
            ...current,
            activities: [...current.activities, activity],
          });
          this.activityTitle.set("");
          this.activityDescription.set("");
          this.activityDueDate.set("");
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao adicionar atividade."));
          this.loading.set(false);
        },
      });
  }

  toggleActivityDone(activity: SpecialProjectActivityRecord): void {
    const project = this.selectedProject();
    if (!project || !this.canWrite()) {
      return;
    }
    const nextStatus = activity.status === "DONE" ? "OPEN" : "DONE";
    this.loading.set(true);
    this.salesFlowService
      .updateSpecialProjectActivity(project.id, activity.id, { status: nextStatus })
      .subscribe({
        next: (updated) => {
          const current = this.selectedProject();
          if (!current) {
            return;
          }
          this.selectedProject.set({
            ...current,
            activities: current.activities.map((item) => (item.id === updated.id ? updated : item)),
          });
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao atualizar atividade."));
          this.loading.set(false);
        },
      });
  }

  removeActivity(activity: SpecialProjectActivityRecord): void {
    const project = this.selectedProject();
    if (!project || !this.canWrite()) {
      return;
    }
    if (!window.confirm("Excluir atividade?")) {
      return;
    }
    this.loading.set(true);
    this.salesFlowService.deleteSpecialProjectActivity(project.id, activity.id).subscribe({
      next: () => {
        const current = this.selectedProject();
        if (!current) {
          return;
        }
        this.selectedProject.set({
          ...current,
          activities: current.activities.filter((item) => item.id !== activity.id),
        });
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.parseError(err, "Erro ao excluir atividade."));
        this.loading.set(false);
      },
    });
  }

  uploadDocuments(event: Event): void {
    const project = this.selectedProject();
    if (!project || !this.canWrite()) {
      return;
    }
    const input = event.target as HTMLInputElement;
    const files = input.files;
    if (!files || files.length === 0) {
      return;
    }

    const queue = Array.from(files);
    this.loading.set(true);

    const uploadNext = () => {
      const file = queue.shift();
      if (!file) {
        this.loading.set(false);
        input.value = "";
        return;
      }

      this.salesFlowService
        .uploadSpecialProjectDocument(project.id, file, file.name)
        .subscribe({
          next: (doc) => {
            const current = this.selectedProject();
            if (current) {
              this.selectedProject.set({
                ...current,
                documents: [doc, ...current.documents],
              });
            }
            uploadNext();
          },
          error: (err) => {
            this.error.set(this.parseError(err, `Erro ao enviar arquivo ${file.name}.`));
            this.loading.set(false);
            input.value = "";
          },
        });
    };

    uploadNext();
  }

  removeDocument(doc: SpecialProjectDocumentRecord): void {
    const project = this.selectedProject();
    if (!project || !this.canWrite()) {
      return;
    }
    if (!window.confirm("Excluir documento?")) {
      return;
    }

    this.loading.set(true);
    this.salesFlowService.deleteSpecialProjectDocument(project.id, doc.id).subscribe({
      next: () => {
        const current = this.selectedProject();
        if (!current) {
          return;
        }
        this.selectedProject.set({
          ...current,
          documents: current.documents.filter((item) => item.id !== doc.id),
        });
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.parseError(err, "Erro ao excluir documento."));
        this.loading.set(false);
      },
    });
  }

  private refreshProjectInList(updated: SpecialProjectRecord): void {
    this.projects.set(this.projects().map((item) => (item.id === updated.id ? updated : item)));
  }
}
