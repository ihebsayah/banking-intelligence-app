// src/types/auth.ts
export interface User {
  user_id: string;
  email: string;
  name: string;
  role: 'analyst' | 'manager' | 'compliance' | 'admin';
  bank_id: string;
  branch_id?: string;
  created_at: string;
  last_login: string;
  permissions: string[];
  legacy_role?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}
