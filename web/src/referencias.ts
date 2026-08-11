/**
 * "¿Compro ya o espero?", que es la pregunta de verdad al mirar un billete.
 *
 * El precio de hoy a secas no la responde: 30 € puede ser un chollo o un robo
 * según lo que suela costar ESE viaje. La respuesta necesita histórico, y por
 * eso la app calla mientras no lo tiene en vez de inventarse un veredicto con
 * dos días de datos. `referencias.json` trae un `listo` justo para eso.
 */

import type { Referencia, Referencias, Tren } from './tipos'

export type Veredicto = {
  /** Cuánto se desvía del precio normal, en porcentaje (negativo = barato). */
  desvio: number
  normal: number
  etiqueta: string
  tono: 'chollo' | 'bien' | 'normal' | 'caro'
}

/**
 * Umbrales del veredicto. Un billete que se mueve un 10 % arriba o abajo no
 * merece que se le llame nada: es la variación de cualquier día.
 */
const CHOLLO = -25
const BIEN = -10
const CARO = 15

export function rutaDe(tren: Pick<Tren, 'origen_id' | 'destino_id'>): string {
  return `${tren.origen_id}->${tren.destino_id}`
}

/** Qué suele costar ese viaje ese día, o null si aún no se sabe. */
export function referenciaDe(
  datos: Referencias | null,
  tren: Pick<Tren, 'origen_id' | 'destino_id' | 'fecha'>,
): Referencia | null {
  if (!datos?.listo) return null
  return datos.viajes[rutaDe(tren)]?.[tren.fecha] ?? null
}

export function valorar(
  datos: Referencias | null,
  tren: Pick<Tren, 'origen_id' | 'destino_id' | 'fecha' | 'precio'>,
): Veredicto | null {
  const referencia = referenciaDe(datos, tren)
  if (!referencia || referencia.normal <= 0) return null

  const desvio = ((tren.precio - referencia.normal) / referencia.normal) * 100
  const comun = { desvio, normal: referencia.normal }

  if (desvio <= CHOLLO)
    return { ...comun, tono: 'chollo', etiqueta: `${Math.abs(Math.round(desvio))}% bajo lo normal` }
  if (desvio <= BIEN)
    return { ...comun, tono: 'bien', etiqueta: 'Mejor de lo normal' }
  if (desvio >= CARO)
    return { ...comun, tono: 'caro', etiqueta: `${Math.round(desvio)}% sobre lo normal` }
  return { ...comun, tono: 'normal', etiqueta: 'Precio de siempre' }
}

/** Cuánto falta para poder opinar. null cuando ya se puede. */
export function loQueFalta(datos: Referencias | null): string | null {
  if (!datos || datos.listo) return null
  const faltan = Math.max(0, datos.dias_necesarios - datos.dias_reunidos)
  if (faltan === 0) return null
  return faltan === 1
    ? 'Falta un día de precios para poder decirte si un billete está barato.'
    : `Faltan ${faltan} días de precios para poder decirte si un billete está barato.`
}
