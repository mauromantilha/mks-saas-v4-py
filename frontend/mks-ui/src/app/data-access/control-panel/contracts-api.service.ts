import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import { ContractDto, PaginatedResponseDto, SendContractDto } from "./control-panel.dto";

@Injectable({ providedIn: "root" })
export class ContractsApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly tenantsUrl = buildApiUrl(this.config, "/api/control-panel/tenants/");
  private readonly contractsUrl = buildApiUrl(this.config, "/api/control-panel/contracts/");

  listContracts(tenantId: number): Observable<ContractDto[] | PaginatedResponseDto<ContractDto>> {
    return this.http.get<ContractDto[] | PaginatedResponseDto<ContractDto>>(
      `${this.tenantsUrl}${tenantId}/contracts/`
    );
  }

  createContract(tenantId: number): Observable<ContractDto> {
    return this.http.post<ContractDto>(`${this.tenantsUrl}${tenantId}/contracts/`, {});
  }

  sendContract(contractId: number, payload: SendContractDto): Observable<ContractDto> {
    return this.http.post<ContractDto>(`${this.contractsUrl}${contractId}/send/`, payload);
  }

  getContract(contractId: number): Observable<ContractDto> {
    return this.http.get<ContractDto>(`${this.contractsUrl}${contractId}/`);
  }
}
