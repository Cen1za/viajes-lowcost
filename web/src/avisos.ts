/**
 * Avisos como notificación del móvil, sin depender de Telegram.
 *
 * Aquí no hay servidor: quien manda las notificaciones es GitHub Actions. Para
 * poder hacerlo necesita la "suscripción" que el navegador entrega al dar
 * permiso, y ese dato se guarda a mano como secreto del repositorio.
 *
 * Puede parecer rudimentario, pero es a propósito: la alternativa era montar
 * un servidor solo para almacenar una línea de texto que cambia una vez al
 * año. Y como el repositorio es público, la suscripción NO puede vivir en él:
 * contiene un endpoint único que permite mandar notificaciones a este móvil.
 */

/**
 * Mitad pública del par de claves VAPID. Se genera una vez con:
 *
 *     python -m buscador claves-push
 *
 * Vacía = los avisos por notificación están sin configurar, y la app lo dice
 * en Ajustes en vez de ofrecer un botón que no haría nada.
 */
export const CLAVE_PUBLICA = ''

export type EstadoAvisos =
  | 'sin-configurar' // falta la clave pública
  | 'no-soportado' // el navegador no tiene Web Push (iOS sin instalar, por ejemplo)
  | 'bloqueado' // el usuario dijo que no en su día
  | 'activo' // ya suscrito en este dispositivo
  | 'disponible' // se puede activar

export function estadoAvisos(): EstadoAvisos {
  if (!CLAVE_PUBLICA) return 'sin-configurar'
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return 'no-soportado'
  if (Notification.permission === 'denied') return 'bloqueado'
  if (Notification.permission === 'granted') return 'activo'
  return 'disponible'
}

/**
 * La clave viaja en base64url y el navegador la quiere en bytes.
 *
 * Se reserva el ArrayBuffer explícitamente en vez de usar `Uint8Array.from`:
 * así el tipo resultante es el que `applicationServerKey` acepta, sin tener
 * que forzarlo con un cast.
 */
function aBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const relleno = '='.repeat((4 - (base64url.length % 4)) % 4)
  const base64 = (base64url + relleno).replace(/-/g, '+').replace(/_/g, '/')
  const crudo = atob(base64)

  const bytes = new Uint8Array(new ArrayBuffer(crudo.length))
  for (let i = 0; i < crudo.length; i += 1) bytes[i] = crudo.charCodeAt(i)
  return bytes
}

/**
 * Pide permiso y devuelve la suscripción en texto, lista para pegar en el
 * secreto WEB_PUSH_SUSCRIPCION. Devuelve null si el usuario no da permiso.
 */
export async function activarAvisos(): Promise<string | null> {
  if (!CLAVE_PUBLICA) throw new Error('Falta la clave pública: genera las claves primero.')

  const permiso = await Notification.requestPermission()
  if (permiso !== 'granted') return null

  const registro = await navigator.serviceWorker.ready
  // Si ya había una suscripción se reutiliza: pedir otra dejaría la anterior
  // viva y el servidor mandaría el aviso dos veces al mismo móvil.
  const existente = await registro.pushManager.getSubscription()
  const suscripcion =
    existente ??
    (await registro.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: aBytes(CLAVE_PUBLICA),
    }))

  return JSON.stringify(suscripcion.toJSON())
}

/** Deja de recibir notificaciones en este dispositivo. */
export async function desactivarAvisos(): Promise<boolean> {
  const registro = await navigator.serviceWorker.ready
  const suscripcion = await registro.pushManager.getSubscription()
  return suscripcion ? suscripcion.unsubscribe() : false
}
