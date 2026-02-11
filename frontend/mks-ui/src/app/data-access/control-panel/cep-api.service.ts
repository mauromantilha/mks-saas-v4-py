import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import { CepLookupResponseDto } from "./control-panel.dto";

function onlyDigits(value: string): string {
  return (value || "").replace(/\D/g, "");
}

@Injectable({ providedIn: "root" })
export class CepApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly baseUrl = buildApiUrl(this.config, "/control-panel/utils/cep/");

  lookupCep(cep: string): Observable<CepLookupResponseDto> {
    const normalizedCep = onlyDigits(cep);
    return this.http.get<CepLookupResponseDto>(`${this.baseUrl}${normalizedCep}/`);
  }
}

