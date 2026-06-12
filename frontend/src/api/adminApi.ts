// src/api/adminApi.ts
import { apiClient } from './client';
import type { AdminUser } from '../types/api';

export const adminApi = {
  getUsers: async (): Promise<AdminUser[]> => {
    const res = await apiClient.get<AdminUser[]>('/admin/users');
    return res.data;
  },

  getSystemHealth: async (): Promise<any> => {
    const res = await apiClient.get('/health');
    return res.data;
  }
};
