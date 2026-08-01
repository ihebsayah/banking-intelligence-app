// src/api/notificationsApi.ts
import { apiClient } from './client';
import type {
  MarkAllReadResponse,
  NotificationListResponse,
  NotificationMutationResponse,
} from '../types/alerts';

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export interface NotificationListParams {
  isRead?: boolean;
  page?: number;
  perPage?: number;
}

export const notificationsApi = {
  list: async (params: NotificationListParams = {}): Promise<NotificationListResponse> => {
    const qs = new URLSearchParams();
    if (params.isRead !== undefined) qs.append('is_read', String(params.isRead));
    qs.append('page', String(params.page ?? 1));
    qs.append('per_page', String(params.perPage ?? 50));
    const res = await apiClient.get<NotificationListResponse>(`/notifications?${qs.toString()}`);
    return res.data;
  },

  markRead: async (notificationId: string): Promise<NotificationMutationResponse> => {
    const res = await apiClient.patch<NotificationMutationResponse>(
      `/notifications/${notificationId}/read`,
      {},
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } },
    );
    return res.data;
  },

  markAllRead: async (): Promise<MarkAllReadResponse> => {
    const res = await apiClient.patch<MarkAllReadResponse>(
      '/notifications/read-all',
      {},
      { headers: { 'X-Request-ID': uuid(), 'X-Idempotency-Key': uuid() } },
    );
    return res.data;
  },
};
