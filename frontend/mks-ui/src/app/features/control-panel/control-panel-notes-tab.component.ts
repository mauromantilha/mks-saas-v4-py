import { CommonModule } from "@angular/common";
import { Component, Input, OnChanges, SimpleChanges, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { finalize } from "rxjs";

import { PermissionDirective } from "../../core/auth/permission.directive";
import { ToastService } from "../../core/ui/toast.service";
import {
  PaginatedResponseDto,
  TenantInternalNoteDto,
} from "../../data-access/control-panel/control-panel.dto";
import { TenantNotesApi } from "../../data-access/control-panel/tenant-notes-api.service";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";

@Component({
  selector: "app-control-panel-notes-tab",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    PermissionDirective,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-notes-tab.component.html",
  styleUrl: "./control-panel-notes-tab.component.scss",
})
export class ControlPanelNotesTabComponent implements OnChanges {
  @Input({ required: true }) tenantId!: number;

  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal("");
  readonly notes = signal<TenantInternalNoteDto[]>([]);
  readonly draft = signal("");

  constructor(
    private readonly notesApi: TenantNotesApi,
    private readonly toast: ToastService
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes["tenantId"] && this.tenantId) {
      this.reload();
    }
  }

  reload(): void {
    if (!this.tenantId) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notesApi
      .listTenantNotes(this.tenantId)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          this.notes.set(this.normalizeResponse(response));
        },
        error: () => {
          this.error.set("Falha ao carregar notas internas.");
          this.notes.set([]);
        },
      });
  }

  createNote(): void {
    if (!this.tenantId || this.saving()) {
      return;
    }

    const note = this.draft().trim();
    if (!note) {
      this.toast.error("Digite uma nota antes de salvar.");
      return;
    }

    this.saving.set(true);
    this.notesApi
      .createTenantNote(this.tenantId, { note })
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (created) => {
          this.notes.update((current) => [created, ...current]);
          this.draft.set("");
          this.toast.success("Nota adicionada com sucesso.");
        },
        error: () => {
          this.toast.error("Falha ao salvar nota.");
        },
      });
  }

  hasError(): boolean {
    return !this.loading() && !!this.error();
  }

  hasEmpty(): boolean {
    return !this.loading() && !this.error() && this.notes().length === 0;
  }

  private normalizeResponse(
    response: TenantInternalNoteDto[] | PaginatedResponseDto<TenantInternalNoteDto>
  ): TenantInternalNoteDto[] {
    if (Array.isArray(response)) {
      return response;
    }
    return response.results ?? [];
  }
}
