// src/api/attachmentsApi.ts
import { apiClient } from './client';
import type { AttachmentListResponse, InvestigationAttachment } from '../types/investigations';

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export const attachmentsApi = {
  upload: async (
    investigationId: string,
    file: File,
    description?: string
  ): Promise<InvestigationAttachment> => {
    const formData = new FormData();
    formData.append('file', file);
    if (description?.trim()) {
      formData.append('description', description.trim());
    }

    const res = await apiClient.post<InvestigationAttachment>(
      `/investigations/${investigationId}/attachments`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          'X-Request-ID': uuid(),
        },
      }
    );
    return res.data;
  },

  list: async (investigationId: string): Promise<AttachmentListResponse> => {
    const res = await apiClient.get<AttachmentListResponse>(
      `/investigations/${investigationId}/attachments`
    );
    return res.data;
  },

  download: async (
    investigationId: string,
    attachmentId: string,
    filename: string
  ): Promise<void> => {
    const res = await apiClient.get<Blob>(
      `/investigations/${investigationId}/attachments/${attachmentId}/download`,
      { responseType: 'blob' }
    );

    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  delete: async (
    investigationId: string,
    attachmentId: string
  ): Promise<{ success: boolean }> => {
    const res = await apiClient.delete<{ success: boolean }>(
      `/investigations/${investigationId}/attachments/${attachmentId}`,
      { headers: { 'X-Request-ID': uuid() } }
    );
    return res.data;
  },
};
