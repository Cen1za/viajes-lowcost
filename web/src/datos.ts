import { useEffect, useState } from 'react'

/**
 * Carga uno de los JSON de data/. El service worker se encarga de que, sin
 * cobertura, se devuelva la última copia descargada.
 */
export function useDatos<T>(nombre: string) {
  const [datos, setDatos] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    let vigente = true
    setCargando(true)

    fetch(`./data/${nombre}.json`, { cache: 'no-cache' })
      .then((r) => {
        if (!r.ok) throw new Error(`No se pudo leer ${nombre}.json (${r.status})`)
        return r.json() as Promise<T>
      })
      .then((d) => vigente && setDatos(d))
      .catch((e: Error) => vigente && setError(e.message))
      .finally(() => vigente && setCargando(false))

    return () => {
      vigente = false
    }
  }, [nombre])

  return { datos, error, cargando }
}

const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
               'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

/** '2026-09-11' -> 'vie 11 sep' */
export function fechaCorta(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number)
  const f = new Date(a, m - 1, d)
  return `${DIAS[f.getDay()].slice(0, 3)} ${d} ${MESES[m - 1]}`
}

/** 181 -> '3h01' */
export function duracion(minutos: number): string {
  return `${Math.floor(minutos / 60)}h${String(minutos % 60).padStart(2, '0')}`
}

export function euros(valor: number): string {
  return `${valor.toFixed(2).replace('.', ',')} €`
}

/** Cuánto hace que se actualizaron los datos, en lenguaje llano. */
export function desde(iso: string): string {
  const minutos = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutos < 2) return 'ahora mismo'
  if (minutos < 60) return `hace ${minutos} min`
  const horas = Math.round(minutos / 60)
  if (horas < 24) return `hace ${horas} h`
  return `hace ${Math.round(horas / 24)} días`
}
