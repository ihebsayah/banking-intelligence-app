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

export async function initKeycloak(): Promise<boolean> {
  const kc = getKeycloak();
  const authenticated = await kc.init({
    onLoad: 'check-sso',
    pkceMethod: 'S256',
    checkLoginIframe: false,
    silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
  });
  return authenticated;
}

export function getKeycloakToken(): string | undefined {
  return keycloakInstance?.token;
}
