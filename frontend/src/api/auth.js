import apiClient from './client';
let client;
let configuration;
let InteractionRequiredAuthError;
let initialization;

export function initializeAuth() {
  initialization ||= initialize();
  return initialization;
}

async function initialize() {
  configuration = (await apiClient.get('/auth/config')).data;
  if (configuration.mode === 'preview' || !configuration.configured) return configuration;
  const msal = await import('@azure/msal-browser');
  const { PublicClientApplication } = msal;
  InteractionRequiredAuthError = msal.InteractionRequiredAuthError;
  client = new PublicClientApplication({
    auth: { clientId: configuration.client_id, authority: `https://login.microsoftonline.com/${configuration.tenant_id}`,
      redirectUri: `${window.location.origin}/redirect.html` }, cache: { cacheLocation: 'sessionStorage' },
  });
  await client.initialize();
  await client.handleRedirectPromise();
  return configuration;
}

export async function accessToken() {
  if (configuration?.mode === 'preview') return null;
  if (!client) throw new Error('Microsoft 365 sign-in is not configured');
  const account = client.getActiveAccount() || client.getAllAccounts()[0];
  if (!account) throw new Error('Sign in to Microsoft 365 to continue');
  try { return (await client.acquireTokenSilent({ scopes: [configuration.scope], account })).accessToken; }
  catch (error) {
    if (error instanceof InteractionRequiredAuthError) throw new Error('Your session needs Microsoft 365 sign-in again. Sign out and sign in to continue.');
    throw error;
  }
}

export async function signIn() {
  if (configuration.mode !== 'preview') {
    const result = await client.loginPopup({ scopes: [configuration.scope] });
    client.setActiveAccount(result.account);
  }
  return (await apiClient.get('/auth/me')).data;
}

export async function signOut() {
  if (client) await client.logoutPopup({ account: client.getActiveAccount(), mainWindowRedirectUri: window.location.origin });
}
