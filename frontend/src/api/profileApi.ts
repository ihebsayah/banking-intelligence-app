// src/api/profileApi.ts
import { apiClient } from './client';
import type { AdminUser } from '../types/api';

export const profileApi = {
  getProfile: async (): Promise<AdminUser> => {
    const res = await apiClient.get<AdminUser>('/auth/me');
    return res.data;
  }
};
