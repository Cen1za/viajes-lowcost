/** Formas de los JSON que genera el buscador en Python (carpeta data/). */

export interface Tren {
  fuente: string
  operador: string
  /** 'ida' (Madrid → Elche) o 'vuelta' (Elche → Madrid). */
  sentido: string
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
  /**
   * Portada del operador. Ninguna web de tren permite enlazar a un billete
   * ni a una búsqueda concreta, así que la app copia los datos del viaje al
   * portapapeles para pegarlos allí.
   */
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
  /** 'ida' o 'vuelta' por ruta. */
  sentidos: Record<string, string>
  /** Qué operador pone el precio más bajo cada día. */
  operadores: Record<string, Record<string, string>>
  /** Horario de ese tren más barato, 'HH:MM–HH:MM'. */
  horarios: Record<string, Record<string, string>>
  rutas: Record<string, Record<string, number>>
}

export interface Fuente {
  fuente: string
  ok: boolean
  ofertas: number
  /** Datos que la web devolvió pero no pasaron el control de credibilidad. */
  descartadas: number
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
  traslado_min: Record<string, number>
  ofertas: Ganga[]
}

/** Campaña anunciada en la portada de una compañía (no un precio de esta ruta). */
export interface Campana {
  huella: string
  compania: string
  texto: string
  /** Fecha en que se vio por primera vez, para saber si es reciente. */
  desde: string
}

export interface Promociones {
  actualizado: string
  campanas: Campana[]
}
