/**
 * Identidad visual de cada operador.
 *
 * El color es lo que permite reconocer de un vistazo quién vende cada billete
 * sin tener que leer: cada tarjeta lleva el borde de su compañía. Los tonos
 * están tomados de las marcas reales, pero ajustados para que todos tengan
 * contraste suficiente sobre blanco.
 */

export interface Compania {
  id: string
  nombre: string
  color: string
  /** Fondo tenue del mismo tono, para chips y etiquetas. */
  suave: string
  descripcion: string
}

export const COMPANIAS: Compania[] = [
  {
    id: 'AVE',
    nombre: 'AVE',
    color: '#6D2077',
    suave: '#F4EBF6',
    descripcion: 'Alta velocidad de Renfe',
  },
  {
    id: 'Avlo',
    nombre: 'Avlo',
    color: '#D6006D',
    suave: '#FDEBF4',
    descripcion: 'Low cost de Renfe',
  },
  {
    id: 'Renfe',
    nombre: 'Renfe',
    color: '#5B2C82',
    suave: '#F1ECF7',
    descripcion: 'Renfe, tipo de tren sin precisar',
  },
  {
    id: 'Ouigo',
    nombre: 'Ouigo',
    color: '#0075BE',
    suave: '#E7F2FA',
    descripcion: 'Low cost de SNCF',
  },
  {
    id: 'iryo',
    nombre: 'iryo',
    color: '#C8102E',
    suave: '#FBEBED',
    descripcion: 'Alta velocidad privada',
  },
]

const POR_ID = new Map(COMPANIAS.map((c) => [c.id.toLowerCase(), c]))

const DESCONOCIDA: Compania = {
  id: 'otro',
  nombre: 'Otro',
  color: '#64748B',
  suave: '#F1F5F9',
  descripcion: 'Operador no identificado',
}

export function compania(operador: string): Compania {
  return POR_ID.get((operador || '').toLowerCase()) ?? DESCONOCIDA
}

/** Compañías presentes en unos resultados, en el orden fijo de COMPANIAS. */
export function companiasPresentes(operadores: string[]): Compania[] {
  const vistos = new Set(operadores.map((o) => compania(o).id))
  const lista = COMPANIAS.filter((c) => vistos.has(c.id))
  return vistos.has(DESCONOCIDA.id) ? [...lista, DESCONOCIDA] : lista
}
