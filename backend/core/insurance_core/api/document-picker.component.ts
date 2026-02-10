import { Component, EventEmitter, Input, Output } from '@angular/core';
import { DocumentUploadService, UploadState } from './document-upload.service';

@Component({
  selector: 'app-document-picker',
  template: `
    <div class="document-picker">
      <div class="drop-zone" (click)="fileInput.click()" (drop)="onDrop($event)" (dragover)="onDragOver($event)">
        <p>Clique ou arraste arquivos aqui</p>
        <input #fileInput type="file" multiple (change)="onFileSelected($event)" style="display:none">
      </div>

      <div class="uploads-list" *ngIf="uploads.length > 0">
        <div *ngFor="let upload of uploads" class="upload-item">
          <div class="file-info">
            <span class="name">{{ upload.file.name }}</span>
            <span class="size">{{ (upload.file.size / 1024) | number:'1.0-2' }} KB</span>
          </div>
          <div class="progress-container">
            <div class="progress-bar" [style.width.%]="upload.progress" [class.error]="upload.status === 'ERROR'"></div>
          </div>
          <div class="status">
            <span *ngIf="upload.status === 'UPLOADING'">Enviando... {{ upload.progress }}%</span>
            <span *ngIf="upload.status === 'CONFIRMING'">Confirmando...</span>
            <span *ngIf="upload.status === 'COMPLETED'" class="text-success">Concluído</span>
            <span *ngIf="upload.status === 'ERROR'" class="text-error">{{ upload.error }}</span>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .drop-zone { border: 2px dashed #ccc; padding: 20px; text-align: center; cursor: pointer; border-radius: 4px; background: #f9f9f9; }
    .drop-zone:hover { border-color: #007bff; background: #f0f7ff; }
    .upload-item { margin-top: 10px; border: 1px solid #eee; padding: 10px; border-radius: 4px; background: white; }
    .file-info { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 0.9em; }
    .progress-container { height: 4px; background: #eee; border-radius: 2px; overflow: hidden; }
    .progress-bar { height: 100%; background: #007bff; transition: width 0.3s; }
    .progress-bar.error { background: #dc3545; }
    .status { font-size: 0.8em; margin-top: 5px; color: #666; }
    .text-success { color: #28a745; font-weight: 500; }
    .text-error { color: #dc3545; }
  `]
})
export class DocumentPickerComponent {
  @Input() entityType!: 'POLICY' | 'ENDORSEMENT' | 'CLAIM';
  @Input() entityId!: number;
  @Input() documentType: string = 'OTHER';
  @Output() uploadComplete = new EventEmitter<void>();

  uploads: UploadState[] = [];

  constructor(private uploadService: DocumentUploadService) {}

  onFileSelected(event: any) {
    const files = event.target.files;
    if (files) this.processFiles(files);
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    if (event.dataTransfer?.files) this.processFiles(event.dataTransfer.files);
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
  }

  processFiles(fileList: FileList) {
    for (let i = 0; i < fileList.length; i++) {
      this.startUpload(fileList[i]);
    }
  }

  startUpload(file: File) {
    const req = { entity_type: this.entityType, entity_id: this.entityId, document_type: this.documentType };
    
    this.uploadService.upload(file, req).subscribe(state => {
      const index = this.uploads.findIndex(u => u.file === file);
      if (index === -1) this.uploads.push(state);
      else this.uploads[index] = state;

      if (state.status === 'COMPLETED') this.uploadComplete.emit();
    });
  }
}