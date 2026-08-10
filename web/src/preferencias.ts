/**
 * Preferencias del usuario, guardadas en el propio móvil.
 *
 * No van en el repositorio a propósito: son tuyas, cambian a menudo y quieres
 * poder tocarlas desde el teléfono sin editar un YAML ni esperar a un
 * despliegue.
 */

import { useCallback, useEffect, useState } from 'react'

export interface Franja {
  id: string
  nombre: string
  desde: number
  hasta: number
}

//: Sin emojis a propósito: en Android se dibujan como bloques de color que
//: ensucian los chips y no aportan nada que no diga ya el texto.
export const FRANJAS: Franja[] = [
  { id: 'madrugada', nombre: 'Madrugada', desde: 0, hasta: 7 },
  { id: 'manana', nombre: 'Mañana', desde: 7, hasta: 13 },
  { id: 'tarde', nombre: 'Tarde', desde: 13, hasta: 19 },
  { id: 'noche', nombre: 'Noche', desde: 19, hasta: 24 },
]

/** '07–13h', para acompañar al nombre de la franja. */
export function horasFranja(f: Franja): string {
  return `${String(f.desde).padStart(2, '0')}–${String(f.hasta).padStart(2, '0')}h`
}

export interface Preferencias {
  /** Ids de FRANJAS. Vacío = cualquier hora vale. */
  franjas: string[]
  /** Ids de compañía. Vacío = todas. */
  companias: string[]
  /** 'todo' | 'ida' | 'vuelta' */
  sentido: string
  /** Ocultar los trenes que llegan a Alicante y obligan a un traslado. */
  soloDirectos: boolean
}

const POR_DEFECTO: Preferencias = {
  franjas: [],
  companias: [],
  sentido: 'todo',
  soloDirectos: false,
}

const CLAVE = 'viajes-lowcost:preferencias'

function leer(): Preferencias {
  try {
    const guardado = localStorage.getItem(CLAVE)
    return guardado ? { ...POR_DEFECTO, ...JSON.parse(guardado) } : POR_DEFECTO
  } catch {
    return POR_DEFECTO
  }
}

export function usePreferencias() {
  const [prefs, setPrefs] = useState<Preferencias>(leer)

  useEffect(() => {
    try {
      localStorage.setItem(CLAVE, JSON.stringify(prefs))
    } catch {
      // Modo incógnito o almacenamiento lleno: seguimos con lo que hay en memoria.
    }
  }, [prefs])

  const cambiar = useCallback(
    <C extends keyof Preferencias>(campo: C, valor: Preferencias[C]) =>
      setPrefs((p) => ({ ...p, [campo]: valor })),
    [],
  )

  /** Añade o quita un valor de una lista (chips que se activan y desactivan). */
  const alternar = useCallback(
    (campo: 'franjas' | 'companias', valor: string) =>
      setPrefs((p) => ({
        ...p,
        [campo]: p[campo].includes(valor)
          ? p[campo].filter((v) => v !== valor)
          : [...p[campo], valor],
      })),
    [],
  )

  const limpiar = useCallback(() => setPrefs(POR_DEFECTO), [])

  return { prefs, cambiar, alternar, limpiar }
}

/** ¿Encaja una hora 'HH:MM' en alguna de las franjas elegidas? */
export function enFranja(hora: string, franjas: string[]): boolean {
  if (!franjas.length) return true
  const h = Number(hora.slice(0, 2))
  return FRANJAS.filter((f) => franjas.includes(f.id)).some(
    (f) => h >= f.desde && h < f.hasta,
  )
}

export function nombreFranja(hora: string): string {
  const h = Number(hora.slice(0, 2))
  return FRANJAS.find((f) => h >= f.desde && h < f.hasta)?.nombre ?? ''
}
