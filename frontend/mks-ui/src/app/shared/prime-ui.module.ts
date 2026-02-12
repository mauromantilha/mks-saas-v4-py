import { NgModule } from "@angular/core";
import { ButtonModule } from "primeng/button";
import { CardModule } from "primeng/card";
import { CheckboxModule } from "primeng/checkbox";
import { InputTextModule } from "primeng/inputtext";
import { TableModule } from "primeng/table";
import { TextareaModule } from "primeng/textarea";

@NgModule({
  exports: [
    ButtonModule,
    CardModule,
    CheckboxModule,
    InputTextModule,
    TableModule,
    TextareaModule,
  ],
})
export class PrimeUiModule {}
