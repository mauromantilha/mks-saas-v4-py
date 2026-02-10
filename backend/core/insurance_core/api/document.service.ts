import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface DocumentUploadRequest {
  entity_type: 'POLICY' | 'ENDORSEMENT' | 'CLAIM';
  entity_id: number;
  file_name: string;
  content_type: string;
  file_size: number;
  document_type?: string;
}

export interface DocumentUploadResponse {
  document_id: number;
  upload_url: string;
  storage_key: string;
  expiration_minutes: number;
}

export interface DocumentDownloadResponse {
  download_url: string;
}

export interface PolicyDocument {
  id: number;
  file_name: string;
  document_type: string;
  created_at: string;
  uploaded_at?: string;
  file_size?: number;
  content_type?: string;
  claim?: { id: number };
  endorsement?: { id: number };
}

@Injectable({
  providedIn: 'root'
})
export class DocumentService {
  private readonly API_URL = '/api/insurance/documents';

  constructor(private http: HttpClient) {}

  list(policyId: number): Observable<PolicyDocument[]> {
    return this.http.get<PolicyDocument[]>(`/api/insurance/policies/${policyId}/documents/`);
  }

  getSignedUploadUrl(data: DocumentUploadRequest): Observable<DocumentUploadResponse> {
    return this.http.post<DocumentUploadResponse>(`${this.API_URL}/signed-upload-url/`, data);
  }

  confirmUpload(documentId: number): Observable<PolicyDocument> {
    return this.http.post<PolicyDocument>(`${this.API_URL}/${documentId}/confirm-upload/`, {});
  }

  uploadToStorage(url: string, file: File): Observable<any> {
    return this.http.put(url, file, {
      headers: { 'Content-Type': file.type },
      reportProgress: true,
      observe: 'events'
    });
  }

  getSignedDownloadUrl(documentId: number, disposition: 'attachment' | 'inline' = 'attachment'): Observable<DocumentDownloadResponse> {
    const params = new HttpParams().set('disposition', disposition);
    return this.http.get<DocumentDownloadResponse>(`${this.API_URL}/${documentId}/download-url/`, { params });
  }

  delete(documentId: number): Observable<void> {
    return this.http.delete<void>(`${this.API_URL}/${documentId}/`);
  }
}