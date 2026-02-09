import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";

import { environment } from "../../../environments/environment";
import { LedgerEntry } from "./ledger.types";

@Injectable({ providedIn: "root" })
export class LedgerService {
  constructor(private readonly http: HttpClient) {}

  list(limit = 200) {
    const bounded = Math.max(1, Math.min(limit, 1000));
    return this.http.get<LedgerEntry[]>(
      `${environment.apiBaseUrl}/api/ledger/?limit=${bounded}`
    );
  }
}

