// src/api/auth.ts
import { apiClient } from './client';
import type { LoginResponse } from '../types/auth';

interface BackendLoginResponse {
  access_token: string;
  user_id: string;
  user_role: string;
  expires_in: number;
}

export const authApi = {
  login: async (data: { email: string; password: string }): Promise<LoginResponse> => {
    const params = new URLSearchParams();
    params.append('username', data.email);
    params.append('password', data.password);

    const res = await apiClient.post<BackendLoginResponse>('/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    const { access_token, user_id, user_role } = res.data;

    return {
      access_token,
      token_type: 'bearer',
      user: {
        user_id,
        email: data.email,
        name: user_id,
        role: user_role as 'analyst' | 'manager' | 'compliance' | 'admin',
        bank_id: 'default',
        created_at: new Date().toISOString(),
        last_login: new Date().toISOString(),
      },
    };
  },

  logout: async () => {
    try { await apiClient.post('/auth/logout'); } catch { /* ignore */ }
  },

  me: async () => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },
};
