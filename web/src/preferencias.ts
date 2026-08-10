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

//: Días de la semana en el orden en que se leen aquí, con el índice que
//: devuelve Date.getDay() (0 = domingo).
export const DIAS_SEMANA = [
  { dia: 1, corto: 'L', nombre: 'Lunes' },
  { dia: 2, corto: 'M', nombre: 'Martes' },
  { dia: 3, corto: 'X', nombre: 'Miércoles' },
  { dia: 4, corto: 'J', nombre: 'Jueves' },
  { dia: 5, corto: 'V', nombre: 'Viernes' },
  { dia: 6, corto: 'S', nombre: 'Sábado' },
  { dia: 0, corto: 'D', nombre: 'Domingo' },
]

export interface Preferencias {
  /** Ids de FRANJAS. Vacío = cualquier hora vale. */
  franjas: string[]
  /** Ids de compañía. Vacío = todas. */
  companias: string[]
  /**
   * Días en los que quieres SALIR e índices de Date.getDay().
   * Por defecto viernes (ida) y lunes (vuelta): la escapada de fin de semana.
   * Vacío = cualquier día de los recopilados.
   */
  diasIda: number[]
  /** Días en los que quieres VOLVER. */
  diasVuelta: number[]
  /** 'todo' | 'ida' | 'vuelta' */
  sentido: string
  /** Ocultar los trenes que llegan a Alicante y obligan a un traslado. */
  soloDirectos: boolean
}

const POR_DEFECTO: Preferencias = {
  franjas: [],
  companias: [],
  diasIda: [5], // viernes
  diasVuelta: [1], // lunes
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

  const alternarDia = useCallback(
    (campo: 'diasIda' | 'diasVuelta', dia: number) =>
      setPrefs((p) => ({
        ...p,
        [campo]: p[campo].includes(dia)
          ? p[campo].filter((d) => d !== dia)
          : [...p[campo], dia],
      })),
    [],
  )

  const limpiar = useCallback(() => setPrefs(POR_DEFECTO), [])

  return { prefs, cambiar, alternar, alternarDia, limpiar }
}

/** ¿Cae esa fecha en alguno de los días de la semana elegidos? */
export function enDia(fechaIso: string, dias: number[]): boolean {
  if (!dias.length) return true
  const [a, m, d] = fechaIso.split('-').map(Number)
  return dias.includes(new Date(a, m - 1, d).getDay())
}

/** Los días que aplican a un viaje según vaya o vuelva. */
export function diasDelSentido(prefs: Preferencias, sentido: string): number[] {
  return sentido === 'vuelta' ? prefs.diasVuelta : prefs.diasIda
}

export function nombreDia(dia: number): string {
  return DIAS_SEMANA.find((d) => d.dia === dia)?.nombre ?? ''
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
