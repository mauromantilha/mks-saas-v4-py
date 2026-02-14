import { CommonModule } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";
import { forkJoin } from "rxjs";

import { TenantMembersService } from "../../core/api/tenant-members.service";
import {
  BankCatalogItem,
  MembershipRole,
  TenantProducer,
  TenantProducerPerformanceResponse,
} from "../../core/api/tenant-members.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-members-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule],
  templateUrl: "./tenant-members-page.component.html",
  styleUrl: "./tenant-members-page.component.scss",
})
export class TenantMembersPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly isOwner = computed(() => this.session()?.role === "OWNER" || this.session()?.role === "MANAGER");

  loading = signal(false);
  error = signal("");
  notice = signal("");
  producerAction = signal("CADASTRAR");
  producers = signal<TenantProducer[]>([]);
  performance = signal<TenantProducerPerformanceResponse | null>(null);
  banks = signal<BankCatalogItem[]>([]);

  fullName = signal("");
  username = signal("");
  email = signal("");
  role = signal<MembershipRole>("MEMBER");
  cpf = signal("");
  teamName = signal("");
  isTeamManager = signal(false);
  zipCode = signal("");
  street = signal("");
  streetNumber = signal("");
  addressComplement = signal("");
  neighborhood = signal("");
  city = signal("");
  state = signal("");
  commissionTransferPercent = signal("20");
  payoutHoldDays = signal("3");
  bankCode = signal("");
  bankName = signal("");
  bankAgency = signal("");
  bankAccount = signal("");
  bankAccountType = signal("");
  pixKeyType = signal("");
  pixKey = signal("");
  isActive = signal(true);

  readonly roles: MembershipRole[] = ["MEMBER", "MANAGER", "OWNER"];
  readonly accountTypeOptions = [
    { label: "Conta Corrente", value: "CHECKING" },
    { label: "Conta Poupança", value: "SAVINGS" },
    { label: "Conta Pagamento", value: "PAYMENT" },
  ];
  readonly pixKeyTypeOptions = [
    { label: "CPF", value: "CPF" },
    { label: "CNPJ", value: "CNPJ" },
    { label: "Email", value: "EMAIL" },
    { label: "Telefone", value: "PHONE" },
    { label: "Aleatória", value: "RANDOM" },
  ];
  readonly actionOptions = [
    { label: "Cadastrar", value: "CADASTRAR" },
    { label: "Atualizar", value: "ATUALIZAR" },
    { label: "Desativar", value: "DESATIVAR" },
  ];

  constructor(
    private readonly tenantMembersService: TenantMembersService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    forkJoin({
      producerResponse: this.tenantMembersService.listProducers(),
      performanceResponse: this.tenantMembersService.getProducerPerformance(),
      banksResponse: this.tenantMembersService.listBanks(),
    }).subscribe({
      next: ({ producerResponse, performanceResponse, banksResponse }) => {
        this.producers.set(producerResponse.results ?? []);
        this.performance.set(performanceResponse ?? null);
        this.banks.set(banksResponse.results ?? []);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao carregar produtores.");
        this.loading.set(false);
      },
    });
  }

  createOrUpdateMember(): void {
    if (!this.isOwner()) {
      this.error.set("Apenas OWNER/MANAGER pode gerenciar produtores.");
      return;
    }

    if (!this.fullName().trim() || !this.cpf().trim()) {
      this.error.set("Nome e CPF são obrigatórios.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.tenantMembersService
      .upsertProducer({
        username: this.username().trim() || undefined,
        email: this.email().trim() || undefined,
        role: this.role(),
        is_active: this.isActive(),
        full_name: this.fullName().trim(),
        cpf: this.cpf().trim(),
        team_name: this.teamName().trim(),
        is_team_manager: this.isTeamManager(),
        zip_code: this.zipCode().trim(),
        street: this.street().trim(),
        street_number: this.streetNumber().trim(),
        address_complement: this.addressComplement().trim(),
        neighborhood: this.neighborhood().trim(),
        city: this.city().trim(),
        state: this.state().trim(),
        commission_transfer_percent: this.commissionTransferPercent().trim() || "0",
        payout_hold_days: Number.parseInt(this.payoutHoldDays().trim() || "3", 10),
        bank_code: this.bankCode().trim(),
        bank_name: this.bankName().trim(),
        bank_agency: this.bankAgency().trim(),
        bank_account: this.bankAccount().trim(),
        bank_account_type: this.bankAccountType().trim() || undefined,
        pix_key_type: this.pixKeyType().trim() || undefined,
        pix_key: this.pixKey().trim(),
      })
      .subscribe({
        next: () => {
          this.resetCreateForm();
          this.notice.set("Produtor salvo com sucesso.");
          this.load();
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail
              ? JSON.stringify(err.error.detail)
              : "Erro ao salvar membro."
          );
          this.loading.set(false);
        },
      });
  }

  updateRole(member: TenantProducer, nextRole: MembershipRole): void {
    if (!this.isOwner()) {
      this.error.set("Apenas OWNER/MANAGER pode gerenciar produtores.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.tenantMembersService.patchProducer(member.id, { role: nextRole }).subscribe({
      next: () => this.load(),
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao atualizar papel do produtor."
        );
        this.loading.set(false);
      },
    });
  }

  deactivate(member: TenantProducer): void {
    if (!this.isOwner()) {
      this.error.set("Apenas OWNER/MANAGER pode gerenciar produtores.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.tenantMembersService.patchProducer(member.id, { is_active: false }).subscribe({
      next: () => this.load(),
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao desativar produtor."
        );
        this.loading.set(false);
      },
    });
  }

  onBankChange(bankCode: string): void {
    this.bankCode.set(bankCode || "");
    const selected = this.banks().find((bank) => bank.code === bankCode);
    this.bankName.set(selected?.name || "");
  }

  private resetCreateForm(): void {
    this.fullName.set("");
    this.username.set("");
    this.email.set("");
    this.role.set("MEMBER");
    this.cpf.set("");
    this.teamName.set("");
    this.isTeamManager.set(false);
    this.zipCode.set("");
    this.street.set("");
    this.streetNumber.set("");
    this.addressComplement.set("");
    this.neighborhood.set("");
    this.city.set("");
    this.state.set("");
    this.commissionTransferPercent.set("20");
    this.payoutHoldDays.set("3");
    this.bankCode.set("");
    this.bankName.set("");
    this.bankAgency.set("");
    this.bankAccount.set("");
    this.bankAccountType.set("");
    this.pixKeyType.set("");
    this.pixKey.set("");
    this.isActive.set(true);
  }
}
