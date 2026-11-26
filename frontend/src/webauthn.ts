/** WebAuthn JSON <-> browser objects (works on Safari/iOS without parse*FromJSON support). */
const decode = (text: string): ArrayBuffer => {
  const base64 = text.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - text.length % 4) % 4)
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index)
  return bytes.buffer
}
const encode = (buffer: ArrayBuffer | null | undefined): string | null => {
  if (!buffer) return null
  let binary = ''
  for (const byte of new Uint8Array(buffer)) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}
type Json = Record<string, unknown>
type Descriptor = { id: string; type: 'public-key'; transports?: AuthenticatorTransport[] }

export function passkeysSupported(): boolean {
  const host = window.location.hostname
  const ip = /^\d{1,3}(\.\d{1,3}){3}$/.test(host) || host.includes(':')
  return typeof window.PublicKeyCredential === 'function' && !!navigator.credentials && window.isSecureContext && !ip
}

export function creationOptions(options: Json): PublicKeyCredentialCreationOptions {
  const user = options.user as Json
  return {
    ...(options as unknown as PublicKeyCredentialCreationOptions),
    challenge: decode(String(options.challenge)),
    user: { ...(user as unknown as PublicKeyCredentialUserEntity), id: decode(String(user.id)) },
    excludeCredentials: ((options.excludeCredentials as Descriptor[] | undefined) ?? []).map(item => ({ ...item, id: decode(item.id) })),
  }
}

export function requestOptions(options: Json): PublicKeyCredentialRequestOptions {
  return {
    ...(options as unknown as PublicKeyCredentialRequestOptions),
    challenge: decode(String(options.challenge)),
    allowCredentials: ((options.allowCredentials as Descriptor[] | undefined) ?? []).map(item => ({ ...item, id: decode(item.id) })),
  }
}

export function credentialJSON(credential: PublicKeyCredential): Json {
  const response = credential.response as AuthenticatorAttestationResponse & AuthenticatorAssertionResponse
  const body: Json = { clientDataJSON: encode(response.clientDataJSON) }
  if ('attestationObject' in response && response.attestationObject) {
    body.attestationObject = encode(response.attestationObject)
    body.transports = typeof response.getTransports === 'function' ? response.getTransports() : []
  } else {
    body.authenticatorData = encode(response.authenticatorData)
    body.signature = encode(response.signature)
    body.userHandle = encode(response.userHandle)
  }
  return { id: credential.id, rawId: encode(credential.rawId), type: credential.type, response: body,
    clientExtensionResults: credential.getClientExtensionResults?.() ?? {}, authenticatorAttachment: credential.authenticatorAttachment ?? null }
}
