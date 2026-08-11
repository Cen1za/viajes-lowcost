import { useEffect, useState, useSyncExternalStore } from 'react'
import { aplicarTraslados } from './destinos'

/* --- Recarga a petición ---------------------------------------------------- */

/**
 * El botón de actualizar vuelve a pedir los JSON a la red.
 *
 * No dispara una búsqueda nueva —eso lo hace el cron cada hora en el servidor—:
 * lo que hace es tirar de la última foto publicada sin esperar a que el
 * navegador decida refrescar su copia.
 */
let version = 0
let enVuelo = 0
const oyentes = new Set<() => void>()

function avisar() {
  for (const oyente of oyentes) oyente()
}

function suscribir(oyente: () => void) {
  oyentes.add(oyente)
  return () => {
    oyentes.delete(oyente)
  }
}

export function recargarDatos() {
  version += 1
  avisar()
}

/** ¿Queda alguna descarga en curso? Para animar el botón mientras dura. */
export function useActualizando(): boolean {
  return useSyncExternalStore(
    suscribir,
    () => enVuelo > 0,
    () => false,
  )
}

/**
 * Carga uno de los JSON de data/. El service worker se encarga de que, sin
 * cobertura, se devuelva la última copia descargada.
 */
export function useDatos<T>(nombre: string) {
  const [datos, setDatos] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const vuelta = useSyncExternalStore(
    suscribir,
    () => version,
    () => version,
  )

  useEffect(() => {
    let vigente = true
    setCargando(true)
    enVuelo += 1
    avisar()

    fetch(`./data/${nombre}.json`, { cache: 'no-cache' })
      .then((r) => {
        if (!r.ok) throw new Error(`No se pudo leer ${nombre}.json (${r.status})`)
        return r.json() as Promise<T>
      })
      .then((d) => {
        if (!vigente) return
        // Los ficheros que traen trenes traen también los minutos de traslado
        // de cada estación. Se aplican antes de pintar para que el sello
        // "+25 min" y el filtro de directos salgan de la configuración y no
        // de una copia a mano.
        aplicarTraslados((d as { traslado_min?: Record<string, number> }).traslado_min)
        setDatos(d)
        setError(null)
      })
      .catch((e: Error) => vigente && setError(e.message))
      .finally(() => {
        enVuelo -= 1
        avisar()
        if (vigente) setCargando(false)
      })

    return () => {
      vigente = false
    }
  }, [nombre, vuelta])

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

/* --- Agrupación por fin de semana ----------------------------------------- */

/** Días enteros desde una referencia fija, sin que el horario de verano moleste. */
function enDias(f: Date): number {
  return Math.floor(Date.UTC(f.getFullYear(), f.getMonth(), f.getDate()) / 86400000)
}

/** El lunes de la semana de esa fecha. */
function lunesDe(f: Date): Date {
  const l = new Date(f)
  l.setDate(l.getDate() - ((l.getDay() + 6) % 7))
  return l
}

export interface Finde<T> {
  /** Semanas desde la actual: 0 este finde, 1 el que viene. */
  semanas: number
  desde: string
  hasta: string
  minimo: number
  cuantos: number
  dias: { fecha: string; minimo: number; elementos: T[] }[]
}

/**
 * Agrupa por fin de semana de viaje.
 *
 * Un finde no cabe dentro de una semana natural: se sale el jueves o el viernes
 * y se vuelve el lunes, que ya cuenta como semana siguiente. Restando tres días
 * antes de mirar de qué semana es, la vuelta del lunes cae en el mismo grupo
 * que su ida, que es como se piensa un viaje.
 */
export function agruparPorFinde<T extends { fecha: string; precio: number }>(
  elementos: T[],
): Finde<T>[] {
  const grupos = new Map<number, T[]>()

  for (const e of elementos) {
    const f = aFecha(e.fecha)
    f.setDate(f.getDate() - 3)
    const clave = enDias(lunesDe(f))
    const lista = grupos.get(clave)
    if (lista) lista.push(e)
    else grupos.set(clave, [e])
  }

  const estaSemana = enDias(lunesDe(new Date()))

  return [...grupos.entries()]
    .sort(([a], [b]) => a - b)
    .map(([clave, lista]) => {
      const dias = agruparPorDia(lista)
      return {
        semanas: Math.round((clave - estaSemana) / 7),
        desde: dias[0].fecha,
        hasta: dias[dias.length - 1].fecha,
        minimo: Math.min(...dias.map((d) => d.minimo)),
        cuantos: lista.length,
        dias,
      }
    })
}

/** 'Este finde', 'El finde que viene', 'Dentro de 3 semanas'. */
export function nombreFinde(semanas: number): string {
  if (semanas <= 0) return 'Este finde'
  if (semanas === 1) return 'El finde que viene'
  return `Dentro de ${semanas} semanas`
}

/** '11 – 14 sep', o '28 sep – 4 oct' si el finde cambia de mes. */
export function rangoCorto(desde: string, hasta: string): string {
  const a = aFecha(desde)
  const b = aFecha(hasta)
  const mesA = MESES[a.getMonth()]
  const mesB = MESES[b.getMonth()]
  if (desde === hasta) return `${a.getDate()} ${mesA}`
  const inicio = mesA === mesB ? `${a.getDate()}` : `${a.getDate()} ${mesA}`
  return `${inicio} – ${b.getDate()} ${mesB}`
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
