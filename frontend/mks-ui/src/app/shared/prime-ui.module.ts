import { NgModule } from "@angular/core";
import { ButtonModule } from "primeng/button";
import { CardModule } from "primeng/card";
import { CheckboxModule } from "primeng/checkbox";
import { SelectModule } from "primeng/select";
import { InputTextModule } from "primeng/inputtext";
import { RadioButtonModule } from "primeng/radiobutton";
import { SkeletonModule } from "primeng/skeleton";
import { TableModule } from "primeng/table";
import { TextareaModule } from "primeng/textarea";

@NgModule({
  exports: [
    ButtonModule,
    CardModule,
    CheckboxModule,
    SelectModule,
    InputTextModule,
    RadioButtonModule,
    SkeletonModule,
    TableModule,
    TextareaModule,
  ],
})
export class PrimeUiModule {}
