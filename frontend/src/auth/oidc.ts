import { UserManager, WebStorageStateStore, User } from 'oidc-client-ts'

const authority = import.meta.env.VITE_OIDC_AUTHORITY ?? ''
const clientId = import.meta.env.VITE_OIDC_CLIENT_ID ?? ''

export const userManager = new UserManager({
  authority,
  client_id: clientId,
  redirect_uri: window.location.origin,
  post_logout_redirect_uri: window.location.origin,
  response_type: 'code',
  scope: 'openid profile email urn:zitadel:iam:org:project:roles',
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  automaticSilentRenew: true,
})

export async function ensureAuthenticated(): Promise<User> {
  if (window.location.search.includes('code=') && window.location.search.includes('state=')) {
    const user = await userManager.signinRedirectCallback()
    const ret = sessionStorage.getItem('pulse_return_path') || '/'
    sessionStorage.removeItem('pulse_return_path')
    window.history.replaceState({}, '', ret)
    return user
  }

  const existing = await userManager.getUser()
  if (existing && !existing.expired) return existing

  const path = window.location.pathname + window.location.search
  if (path !== '/') sessionStorage.setItem('pulse_return_path', path)
  await userManager.signinRedirect()
  return new Promise(() => {})
}

export async function getAccessToken(): Promise<string | null> {
  const u = await userManager.getUser()
  return u?.access_token ?? null
}

export async function getUsername(): Promise<string> {
  const u = await userManager.getUser()
  return u?.profile?.preferred_username ?? u?.profile?.name ?? ''
}

export async function logout(): Promise<void> {
  await userManager.signoutRedirect()
}
