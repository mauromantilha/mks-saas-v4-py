import { Injectable } from '@angular/core';
import { HttpEventType } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map, switchMap, filter } from 'rxjs/operators';
import { DocumentService, DocumentUploadRequest, PolicyDocument } from './document.service';

export interface UploadState {
  file: File;
  progress: number;
  status: 'PENDING' | 'UPLOADING' | 'CONFIRMING' | 'COMPLETED' | 'ERROR';
  error?: string;
  document?: PolicyDocument;
}

@Injectable({
  providedIn: 'root'
})
export class DocumentUploadService {
  constructor(private documentService: DocumentService) {}

  upload(file: File, request: Omit<DocumentUploadRequest, 'file_name' | 'content_type' | 'file_size'>): Observable<UploadState> {
    const initialState: UploadState = { file, progress: 0, status: 'PENDING' };
    
    // 1. Request Signed URL
    return this.documentService.getSignedUploadUrl({
      ...request,
      file_name: file.name,
      content_type: file.type,
      file_size: file.size
    }).pipe(
      switchMap(response => {
        // 2. PUT to Storage
        return this.documentService.uploadToStorage(response.upload_url, file).pipe(
          map(event => {
            if (event.type === HttpEventType.UploadProgress && event.total) {
              const progress = Math.round((100 * event.loaded) / event.total);
              return { ...initialState, status: 'UPLOADING', progress } as UploadState;
            } else if (event.type === HttpEventType.Response) {
              return { ...initialState, status: 'CONFIRMING', progress: 100, uploadResponse: response } as any;
            }
            return { ...initialState, status: 'UPLOADING' } as UploadState;
          })
        );
      }),
      filter(state => state.status === 'CONFIRMING' || state.status === 'UPLOADING'),
      switchMap((state: any) => {
        if (state.status === 'CONFIRMING') {
          // 3. Confirm Upload
          return this.documentService.confirmUpload(state.uploadResponse.document_id).pipe(
            map(doc => ({ ...initialState, status: 'COMPLETED', progress: 100, document: doc } as UploadState))
          );
        }
        return of(state);
      }),
      catchError(err => of({ ...initialState, status: 'ERROR', error: err.message || 'Upload failed' } as UploadState))
    );
  }
}