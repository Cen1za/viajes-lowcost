/// <reference types="vite/client" />

/**
 * Variables de entorno que se leen al compilar.
 *
 * Declararlas aquí es lo que hace que TypeScript avise si se escribe mal el
 * nombre de una, en vez de dar `undefined` en silencio ya en producción.
 */
interface ImportMetaEnv {
  /**
   * Mitad pública de las claves VAPID, para los avisos por notificación.
   * Se genera con `python -m buscador claves-push`. Sin ella, la app
   * simplemente no ofrece esos avisos.
   */
  readonly VITE_VAPID_PUBLICA?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
