import { CommonModule } from "@angular/common";
import { Component, Inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatDialogModule, MAT_DIALOG_DATA } from "@angular/material/dialog";

import { ContractDto } from "../../data-access/control-panel";

@Component({
  selector: "app-control-panel-contract-details-dialog",
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule],
  templateUrl: "./control-panel-contract-details-dialog.component.html",
  styleUrl: "./control-panel-contract-details-dialog.component.scss",
})
export class ControlPanelContractDetailsDialogComponent {
  constructor(@Inject(MAT_DIALOG_DATA) readonly contract: ContractDto) {}
}
