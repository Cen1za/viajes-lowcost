/**
 * Identidad visual del extremo levantino del viaje.
 *
 * Es un eje de color distinto del de las compañías y responde a otra pregunta:
 * la compañía dice *quién te lleva*, el destino dice *a dónde llegas de verdad*.
 * Alicante sale a menudo más barato pero deja 25 minutos de traslado hasta
 * Elche, y esa diferencia tiene que verse sin leer la letra pequeña.
 *
 * En las vueltas el destino es Madrid, así que lo que se marca es siempre el
 * extremo que no es Madrid: es el que cambia y el que decide.
 */

export interface Destino {
  id: string
  nombre: string
  color: string
  suave: string
  traslado: number
}

export const DESTINOS: Destino[] = [
  {
    id: 'elche_av',
    nombre: 'Elche AV',
    color: '#0F766E',
    suave: '#E6F4F1',
    traslado: 0,
  },
  {
    id: 'alicante',
    nombre: 'Alicante',
    color: '#9A5B00',
    suave: '#FDF3E2',
    traslado: 25,
  },
  {
    id: 'murcia',
    nombre: 'Murcia',
    color: '#9A5B00',
    suave: '#FDF3E2',
    traslado: 50,
  },
]

const POR_ID = new Map(DESTINOS.map((d) => [d.id, d]))

const GENERICO: Destino = {
  id: 'otro',
  nombre: 'Otro',
  color: '#566275',
  suave: '#F1F5F9',
  traslado: 0,
}

/** El extremo del viaje que no es Madrid, venga en el origen o en el destino. */
export function destinoDelViaje(origenId: string, destinoId: string): Destino {
  return POR_ID.get(destinoId) ?? POR_ID.get(origenId) ?? GENERICO
}

export function destino(id: string): Destino {
  return POR_ID.get(id) ?? GENERICO
}
