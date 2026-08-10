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
const MESES_LARGOS = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

/** Convierte '2026-09-11' en Date local, sin sustos de zona horaria. */
export function aFecha(iso: string): Date {
  const [a, m, d] = iso.split('-').map(Number)
  return new Date(a, m - 1, d)
}

/** '2026-09-11' -> 'vie 11 sep' */
export function fechaCorta(iso: string): string {
  const f = aFecha(iso)
  return `${DIAS[f.getDay()].slice(0, 3)} ${f.getDate()} ${MESES[f.getMonth()]}`
}

/** '2026-09-11' -> 'Viernes 11 de septiembre' */
export function fechaLarga(iso: string): string {
  const f = aFecha(iso)
  const dia = DIAS[f.getDay()]
  // Solo la inicial en mayúscula: con text-transform de CSS saldría
  // "Viernes 11 De Septiembre", que en español está mal.
  return `${dia[0].toUpperCase()}${dia.slice(1)} ${f.getDate()} de ${MESES_LARGOS[f.getMonth()]}`
}

/**
 * Agrupa por fecha y ordena por precio dentro de cada día.
 *
 * Es el orden en que se decide un viaje: primero cuándo puedes ir, y solo
 * después cuál sale mejor de precio ese día. Una lista global ordenada por
 * precio mezcla fechas y no ayuda a elegir.
 */
export function agruparPorDia<T extends { fecha: string; precio: number }>(
  elementos: T[],
): { fecha: string; minimo: number; elementos: T[] }[] {
  const porFecha = new Map<string, T[]>()
  for (const e of elementos) {
    const lista = porFecha.get(e.fecha)
    if (lista) lista.push(e)
    else porFecha.set(e.fecha, [e])
  }

  return [...porFecha.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([fecha, lista]) => {
      const ordenados = [...lista].sort((a, b) => a.precio - b.precio)
      return { fecha, minimo: ordenados[0].precio, elementos: ordenados }
    })
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
