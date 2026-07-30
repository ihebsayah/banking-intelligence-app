import Keycloak from 'keycloak-js';
import { env, requireKeycloakEnv } from '../config/env';

let keycloakInstance: Keycloak | null = null;

export function getKeycloak(): Keycloak {
  if (!keycloakInstance) {
    requireKeycloakEnv();
    keycloakInstance = new Keycloak({
      url: env.KEYCLOAK_URL,
      realm: env.KEYCLOAK_REALM,
      clientId: env.KEYCLOAK_CLIENT_ID,
    });
  }
  return keycloakInstance;
}

let initPromise: Promise<boolean> | null = null;

export async function initKeycloak(): Promise<boolean> {
  if (initPromise) return initPromise;   // idempotent: Strict Mode calls this twice
  initPromise = getKeycloak().init({
    onLoad: 'login-required',
    pkceMethod: 'S256',
    checkLoginIframe: false,
    silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
  });
  return initPromise;
}

export function getKeycloakToken(): string | undefined {
  return keycloakInstance?.token;
}
