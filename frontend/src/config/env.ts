// Environment configuration — typed access to Vite env vars
export const env = {
  AUTH_PROVIDER: import.meta.env.VITE_AUTH_PROVIDER ?? 'legacy',
  KEYCLOAK_URL: import.meta.env.VITE_KEYCLOAK_URL ?? '',
  KEYCLOAK_REALM: import.meta.env.VITE_KEYCLOAK_REALM ?? '',
  KEYCLOAK_CLIENT_ID: import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? '',
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL ?? '/api',
} as const;

export function requireKeycloakEnv() {
  const missing: string[] = [];
  if (!env.KEYCLOAK_URL) missing.push('VITE_KEYCLOAK_URL');
  if (!env.KEYCLOAK_REALM) missing.push('VITE_KEYCLOAK_REALM');
  if (!env.KEYCLOAK_CLIENT_ID) missing.push('VITE_KEYCLOAK_CLIENT_ID');
  if (missing.length > 0) {
    throw new Error(`Missing required Keycloak environment variables: ${missing.join(', ')}`);
  }
}
