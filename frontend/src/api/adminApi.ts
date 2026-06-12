// src/api/adminApi.ts
import { apiClient } from './client';
import type { AdminUserRow, RoleInfo, PermissionInfo } from '../types/api';

export const adminApi = {
  getUsers: async (
    page = 1,
    pageSize = 25,
    role?: string,
    status?: string
  ): Promise<AdminUserRow[]> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (role) params.append('role', role);
    if (status) params.append('status', status);

    const res = await apiClient.get<AdminUserRow[]>(`/admin/users?${params.toString()}`);
    return res.data;
  },

  getRoles: async (): Promise<RoleInfo[]> => {
    const res = await apiClient.get<RoleInfo[]>('/admin/roles');
    return res.data;
  },

  getPermissions: async (): Promise<PermissionInfo[]> => {
    const res = await apiClient.get<PermissionInfo[]>('/admin/permissions');
    return res.data;
  },

  getSystemHealth: async (): Promise<any> => {
    const res = await apiClient.get('/health');
    return res.data;
  }
};
