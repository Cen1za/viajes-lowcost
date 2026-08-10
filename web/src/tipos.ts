/** Formas de los JSON que genera el buscador en Python (carpeta data/). */

export interface Tren {
  fuente: string
  operador: string
  origen: string
  destino: string
  origen_id: string
  destino_id: string
  fecha: string
  salida: string
  llegada: string
  duracion_min: number
  precio: number
  tarifa: string | null
  plazas: number | null
  url: string
}

export interface Latest {
  actualizado: string
  traslado_min: Record<string, number>
  trenes: Tren[]
}

export interface Calendario {
  actualizado: string
  /** Nombre legible de cada ruta, p. ej. 'Madrid Chamartín → Elche AV'. */
  nombres: Record<string, string>
  rutas: Record<string, Record<string, number>>
}

export interface Fuente {
  fuente: string
  ok: boolean
  ofertas: number
  duracion_s: number
  error: string | null
}

export interface EstadoFuentes {
  actualizado: string
  fuentes: Fuente[]
}

export interface Ganga extends Tren {
  motivo: string
  mediana: number | null
  caida_pct: number | null
}

export interface Gangas {
  actualizado: string
  ofertas: Ganga[]
}
