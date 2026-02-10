import { Component, Input, OnInit, OnChanges } from '@angular/core';
import { DocumentService, PolicyDocument } from './document.service';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

@Component({
  selector: 'app-document-list',
  template: `
    <div class="document-list">
      <table class="table" *ngIf="documents$ | async as documents">
        <thead>
          <tr>
            <th>Nome</th>
            <th>Tipo</th>
            <th>Data</th>
            <th>Tamanho</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let doc of documents">
            <td>{{ doc.file_name }}</td>
            <td>{{ getLabel(doc.document_type) }}</td>
            <td>{{ doc.created_at | date:'dd/MM/yyyy HH:mm' }}</td>
            <td>{{ (doc.file_size || 0) / 1024 | number:'1.0-2' }} KB</td>
            <td>
              <button *ngIf="canPreview(doc)" (click)="preview(doc)" class="btn-icon" title="Visualizar">👁️</button>
              <button (click)="download(doc)" class="btn-icon" title="Download">⬇️</button>
              <button (click)="delete(doc)" class="btn-icon text-danger" title="Excluir">🗑️</button>
            </td>
          </tr>
          <tr *ngIf="documents.length === 0">
            <td colspan="5" class="text-center">Nenhum documento encontrado.</td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
  styles: [`
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 10px; border-bottom: 1px solid #eee; text-align: left; }
    .btn-icon { background: none; border: none; cursor: pointer; font-size: 1.1em; margin-right: 5px; }
    .text-danger { color: #dc3545; }
    .text-center { text-align: center; color: #666; padding: 20px; }
  `]
})
export class DocumentListComponent implements OnInit, OnChanges {
  @Input() policyId!: number;
  @Input() entityType?: 'POLICY' | 'ENDORSEMENT' | 'CLAIM';
  @Input() entityId?: number;
  
  documents$: Observable<PolicyDocument[]>;

  constructor(private documentService: DocumentService) {}

  ngOnInit() { this.loadDocuments(); }
  ngOnChanges() { this.loadDocuments(); }

  loadDocuments() {
    if (!this.policyId) return;
    
    this.documents$ = this.documentService.list(this.policyId).pipe(
      map(docs => {
        if (this.entityType === 'CLAIM' && this.entityId) return docs.filter(d => d.claim?.id === this.entityId);
        if (this.entityType === 'ENDORSEMENT' && this.entityId) return docs.filter(d => d.endorsement?.id === this.entityId);
        return docs;
      })
    );
  }

  canPreview(doc: PolicyDocument): boolean {
    if (doc.content_type) {
      return doc.content_type === 'application/pdf' || doc.content_type.startsWith('image/');
    }
    const ext = doc.file_name.split('.').pop()?.toLowerCase();
    return ['pdf', 'jpg', 'jpeg', 'png', 'gif'].includes(ext || '');
  }

  preview(doc: PolicyDocument) {
    this.documentService.getSignedDownloadUrl(doc.id, 'inline').subscribe(res => window.open(res.download_url, '_blank'));
  }

  download(doc: PolicyDocument) {
    this.documentService.getSignedDownloadUrl(doc.id).subscribe(res => window.open(res.download_url, '_blank'));
  }

  delete(doc: PolicyDocument) {
    if (confirm('Tem certeza que deseja excluir este documento?')) this.documentService.delete(doc.id).subscribe(() => this.loadDocuments());
  }

  getLabel(type: string): string {
    const labels: any = { 'POLICY': 'Apólice', 'ENDORSEMENT': 'Endosso', 'CLAIM': 'Sinistro', 'BILL': 'Boleto', 'OTHER': 'Outros' };
    return labels[type] || type;
  }
}