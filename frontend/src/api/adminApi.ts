// src/api/adminApi.ts
import { apiClient } from './client';
import type {
  AdminUserRow,
  PaginatedAdminUsers,
  RoleInfo,
  PermissionInfo,
  CreateUserRequest,
  CreateUserResponse,
  UpdateUserRequest,
  UpdateUserStatusRequest,
  UpdateUserRoleRequest,
  ResetPasswordResponse,
  PaginatedActivityLog,
} from '../types/api';

export const adminApi = {
  // ─── User Directory ───────────────────────────────────────────────────────────

  getUsers: async (
    page = 1,
    pageSize = 25,
    role?: string,
    status?: string,
    search?: string
  ): Promise<PaginatedAdminUsers> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (role)   params.append('role', role);
    if (status) params.append('status', status);
    if (search) params.append('search', search);

    const res = await apiClient.get<PaginatedAdminUsers>(`/admin/users?${params.toString()}`);
    // Handle legacy list response (wrap if needed)
    const data = res.data;
    if (Array.isArray(data)) {
      return { total: (data as AdminUserRow[]).length, page, page_size: pageSize, items: data as AdminUserRow[] };
    }
    return data;
  },

  getUserDetail: async (userId: string): Promise<AdminUserRow> => {
    const res = await apiClient.get<AdminUserRow>(`/admin/users/${userId}`);
    return res.data;
  },

  createUser: async (data: CreateUserRequest): Promise<CreateUserResponse> => {
    const res = await apiClient.post<CreateUserResponse>('/admin/users', data);
    return res.data;
  },

  updateUser: async (userId: string, data: UpdateUserRequest): Promise<AdminUserRow> => {
    const res = await apiClient.patch<AdminUserRow>(`/admin/users/${userId}`, data);
    return res.data;
  },

  updateUserStatus: async (userId: string, data: UpdateUserStatusRequest): Promise<{ user_id: string; status: string }> => {
    const res = await apiClient.patch<{ user_id: string; status: string }>(`/admin/users/${userId}/status`, data);
    return res.data;
  },

  updateUserRole: async (userId: string, data: UpdateUserRoleRequest): Promise<{ user_id: string; role: string }> => {
    const res = await apiClient.patch<{ user_id: string; role: string }>(`/admin/users/${userId}/roles`, data);
    return res.data;
  },

  resetPassword: async (userId: string): Promise<ResetPasswordResponse> => {
    const res = await apiClient.post<ResetPasswordResponse>(`/admin/users/${userId}/reset-password`, {});
    return res.data;
  },

  // ─── Role Management ──────────────────────────────────────────────────────────

  getRoles: async (): Promise<RoleInfo[]> => {
    const res = await apiClient.get<RoleInfo[]>('/admin/roles');
    return res.data;
  },

  createRole: async (data: { role_id: string; label: string; description?: string }): Promise<RoleInfo> => {
    const res = await apiClient.post<RoleInfo>('/admin/roles', data);
    return res.data;
  },

  updateRolePermissions: async (roleId: string, permissions: string[]): Promise<{ role_id: string; permissions: string[] }> => {
    const res = await apiClient.patch<{ role_id: string; permissions: string[] }>(
      `/admin/roles/${roleId}/permissions`,
      { permissions }
    );
    return res.data;
  },

  // ─── Permissions Registry ─────────────────────────────────────────────────────

  getPermissions: async (): Promise<PermissionInfo[]> => {
    const res = await apiClient.get<PermissionInfo[]>('/admin/permissions');
    // Normalise permission_key → permission for UI compatibility
    return (res.data as any[]).map((p) => ({
      ...p,
      permission: p.permission ?? p.permission_key,
    }));
  },

  // ─── Activity Log ─────────────────────────────────────────────────────────────

  getActivityLog: async (page = 1, pageSize = 50, actorId?: string): Promise<PaginatedActivityLog> => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (actorId) params.append('actor_id', actorId);
    const res = await apiClient.get<PaginatedActivityLog>(`/admin/activity?${params.toString()}`);
    return res.data;
  },

  // ─── System Health ────────────────────────────────────────────────────────────

  getSystemHealth: async (): Promise<any> => {
    const res = await apiClient.get('/health');
    return res.data;
  },
};
