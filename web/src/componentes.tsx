import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { compania } from './companias'
import { valorar } from './referencias'
import type { Referencias } from './tipos'
import {
  desde,
  duracion,
  euros,
  fechaCorta,
  fechaLarga,
  nombreFinde,
  rangoCorto,
  recargarDatos,
  useActualizando,
} from './datos'
import { destinoDelViaje } from './destinos'
import type { Tren } from './tipos'

/**
 * Lo que suele costar cada viaje, disponible para cualquier tarjeta.
 *
 * Va por contexto y no por props porque las tarjetas se pintan desde cuatro
 * vistas distintas y hacer viajar el dato por toda la jerarquía ensuciaría
 * firmas que no tienen nada que ver con esto. Vale null mientras no haya
 * histórico suficiente, y entonces las tarjetas no dicen nada.
 */
const ContextoReferencias = createContext<Referencias | null>(null)

export function ProveedorReferencias({
  datos,
  children,
}: {
  datos: Referencias | null
  children: ReactNode
}) {
  return (
    <ContextoReferencias.Provider value={datos}>{children}</ContextoReferencias.Provider>
  )
}

/* --- Iconos de la barra inferior (SVG en línea, sin dependencias) --------- */

const trazo = {
  fill: 'none',
  stroke: 'currentColor',
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export const Iconos = {
  ofertas: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <path d="M13 2 4.5 13H11l-1 9 8.5-11H12l1-9Z" />
    </svg>
  ),
  calendario: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <rect x="3" y="5" width="18" height="16" rx="2.5" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  ),
  trenes: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <rect x="5" y="3" width="14" height="13" rx="3" />
      <path d="M5 9h14M8.5 20l-2 2M15.5 20l2 2M7 16h.01M17 16h.01" />
    </svg>
  ),
  ajustes: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <circle cx="16" cy="7" r="2.4" />
      <circle cx="10" cy="17" r="2.4" />
    </svg>
  ),
  reloj: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5.2l3.4 2" />
    </svg>
  ),
  billete: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <path d="M3 9.5V7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2.5a2.5 2.5 0 0 0 0 5V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2.5a2.5 2.5 0 0 0 0-5Z" />
      <path d="M14 5v2M14 11v2M14 17v2" />
    </svg>
  ),
  mapa: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.6" />
    </svg>
  ),
  senal: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <path d="M3 13h4l2.5-7 4 14 2.5-7h5" />
    </svg>
  ),
  movil: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <rect x="6" y="2.5" width="12" height="19" rx="2.5" />
      <path d="M10.5 18.5h3" />
    </svg>
  ),
  recargar: (
    <svg viewBox="0 0 24 24" {...trazo}>
      <path d="M20 12a8 8 0 1 1-2.6-5.9" />
      <path d="M20 3.5V8h-4.5" />
    </svg>
  ),
}

/* --- Piezas sueltas ------------------------------------------------------- */

/**
 * Barra que muestra cuánto falta para la próxima búsqueda.
 *
 * El cron corre a los :05 de cada hora, así que el hueco es predecible y se
 * puede dibujar: se ve de un vistazo si los precios acaban de refrescarse o
 * si están a punto de hacerlo.
 */
export function ProgresoActualizacion({ actualizado }: { actualizado: string }) {
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 30_000)
    return () => clearInterval(t)
  }, [])

  const siguiente = new Date(ahora)
  siguiente.setMinutes(5, 0, 0)
  if (siguiente.getTime() <= ahora) siguiente.setHours(siguiente.getHours() + 1)

  const faltan = Math.max(0, Math.round((siguiente.getTime() - ahora) / 60000))
  const transcurrido = Math.min(100, Math.max(2, ((60 - faltan) / 60) * 100))
  const desfasado = ahora - new Date(actualizado).getTime() > 3 * 3600_000

  return (
    <div className="progreso" title={`Próxima búsqueda en ${faltan} min`}>
      <div className="barra-progreso">
        <span
          className={`relleno${desfasado ? ' desfasado' : ''}`}
          style={{ width: `${transcurrido}%` }}
        />
      </div>
      <span className="leyenda-progreso">
        {desfasado ? (
          <strong>Datos de hace más de 3 h</strong>
        ) : (
          <>Actualizado {desde(actualizado)}</>
        )}
        <span className="siguiente">
          {faltan <= 1 ? 'buscando ahora' : `siguiente en ${faltan} min`}
        </span>
      </span>
    </div>
  )
}

/**
 * Vuelve a pedir los precios publicados.
 *
 * No lanza una búsqueda nueva: eso lo hace el cron en el servidor. Sirve para
 * no tener que esperar a que el navegador refresque su copia, y para saber en
 * el momento si ya ha entrado la búsqueda de la hora en curso.
 */
export function BotonActualizar() {
  const actualizando = useActualizando()

  return (
    <button
      className={`actualizar${actualizando ? ' girando' : ''}`}
      onClick={recargarDatos}
      disabled={actualizando}
      title="Volver a leer los últimos precios publicados"
      aria-label="Actualizar precios"
    >
      {Iconos.recargar}
    </button>
  )
}

/** Cabecera de un fin de semana: cuándo es, qué días cubre y desde cuánto. */
export function CabeceraFinde({
  semanas,
  desde: inicio,
  hasta,
  minimo,
  cuantos,
}: {
  semanas: number
  desde: string
  hasta: string
  minimo: number
  cuantos: number
}) {
  return (
    <div className={`finde${semanas <= 1 ? ' proximo' : ''}`}>
      <span className="cuando">{nombreFinde(semanas)}</span>
      <span className="fechas">{rangoCorto(inicio, hasta)}</span>
      <span className="desde-precio">
        {cuantos} {cuantos === 1 ? 'tren' : 'trenes'} · desde{' '}
        <strong>{euros(minimo)}</strong>
      </span>
    </div>
  )
}

export function Seccion({ titulo, apunte }: { titulo: string; apunte?: ReactNode }) {
  return (
    <div className="seccion">
      <h2>{titulo}</h2>
      {apunte && <span className="apunte">{apunte}</span>}
    </div>
  )
}

/** Cabecera de un día dentro de una lista agrupada por fecha. */
export function CabeceraDia({
  fecha,
  minimo,
  cuantos,
  trenes,
}: {
  fecha: string
  minimo: number
  cuantos: number
  /** Para saber de qué ruta dibujar la evolución: la del tren más barato,
      que es justamente el del "desde X €" que se enseña al lado. */
  trenes?: Tren[]
}) {
  const barato = trenes?.reduce((a, b) => (b.precio < a.precio ? b : a))

  return (
    <div className="dia-cabecera">
      <span className="titulo">{fechaLarga(fecha)}</span>
      <span className="resumen">
        {cuantos} {cuantos === 1 ? 'tren' : 'trenes'} · desde{' '}
        <strong>{euros(minimo)}</strong>
      </span>
      {barato && <Evolucion tren={barato} />}
    </div>
  )
}

/**
 * Cómo se ha movido el precio de este viaje desde que se vigila.
 *
 * Un número suelto no dice si conviene esperar; la forma de la línea sí. Se
 * dibuja a mano en SVG -son cuatro puntos- para no meter una librería de
 * gráficos de cientos de kilobytes en una app que se abre en el andén.
 *
 * No aparece hasta que hay al menos dos días: una línea de un punto no es una
 * evolución, es un adorno.
 */
export function Evolucion({ tren }: { tren: Tren }) {
  const datos = useContext(ContextoReferencias)
  const serie = datos?.series?.[`${tren.origen_id}->${tren.destino_id}`]?.[tren.fecha]
  if (!serie || serie.length < 2) return null

  const precios = serie.map(([, precio]) => precio)
  const alto = 24
  const ancho = 84
  const min = Math.min(...precios)
  const max = Math.max(...precios)
  const recorrido = max - min || 1

  const puntos = precios
    .map((precio, i) => {
      const x = (i / (precios.length - 1)) * ancho
      const y = alto - ((precio - min) / recorrido) * (alto - 4) - 2
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const primero = precios[0]
  const ultimo = precios[precios.length - 1]
  const cambio = ((ultimo - primero) / primero) * 100
  const quieto = Math.abs(cambio) < 1
  const tono = quieto ? 'igual' : cambio < 0 ? 'baja' : 'sube'

  const leyenda = quieto
    ? 'Sin cambios'
    : `${cambio < 0 ? '−' : '+'}${Math.abs(Math.round(cambio))}%`

  return (
    <span
      className={`evolucion ${tono}`}
      title={`Desde que se vigila: ${euros(primero)} → ${euros(ultimo)} en ${serie.length} días`}
    >
      <svg viewBox={`0 0 ${ancho} ${alto}`} width={ancho} height={alto} aria-hidden>
        <polyline points={puntos} fill="none" strokeWidth="2" />
      </svg>
      <em>{leyenda}</em>
    </span>
  )
}

export function Vacio({
  icono,
  titulo,
  children,
}: {
  icono: string
  titulo: string
  children: ReactNode
}) {
  return (
    <div className="vacio">
      <span className="icono">{icono}</span>
      <h3>{titulo}</h3>
      <p>{children}</p>
    </div>
  )
}

export function Cargando() {
  return (
    <div className="lista">
      <div className="esqueleto" />
      <div className="esqueleto" />
      <div className="esqueleto" />
    </div>
  )
}

export function Chip({
  activo,
  onClick,
  color,
  neutro,
  children,
}: {
  activo: boolean
  onClick: () => void
  color?: string
  neutro?: boolean
  children: ReactNode
}) {
  return (
    <button
      className={`chip${neutro ? ' neutro' : ''}`}
      aria-pressed={activo}
      onClick={onClick}
      style={activo && color ? { color, background: '#fff' } : undefined}
    >
      {color && <span className="punto" style={{ background: color }} />}
      {children}
    </button>
  )
}

/* --- Plan de finde (modo "Mejor precio") ---------------------------------- */

/**
 * Un finde resuelto en una tarjeta: la ida y la vuelta más baratas de tus días
 * y el total del viaje.
 *
 * Con la lista completa hay que sumar de cabeza dos precios entre decenas de
 * tarjetas; aquí la cuenta ya está hecha, que es la pregunta real: cuánto me
 * cuesta ir este finde.
 */
export function TarjetaPlan({ ida, vuelta }: { ida?: Tren; vuelta?: Tren }) {
  const total = (ida?.precio ?? 0) + (vuelta?.precio ?? 0)
  const completo = Boolean(ida && vuelta)

  return (
    <article className="plan">
      <div className="plan-total">
        <span>{completo ? 'Ida y vuelta' : ida ? 'Solo ida' : 'Solo vuelta'}</span>
        <strong>{euros(total)}</strong>
      </div>

      {ida && <Tramo tren={ida} />}
      {vuelta && <Tramo tren={vuelta} />}

      {!completo && (
        <p className="plan-aviso">
          {ida
            ? 'Todavía no hay precios de vuelta para tu día.'
            : 'Todavía no hay precios de ida para tu día.'}
        </p>
      )}
    </article>
  )
}

function Tramo({ tren }: { tren: Tren }) {
  const marca = compania(tren.operador)
  const punta = destinoDelViaje(tren.origen_id, tren.destino_id)
  const esVuelta = tren.sentido === 'vuelta'

  return (
    <a
      className="tramo"
      href={tren.url_busqueda || tren.url}
      target="_blank"
      rel="noreferrer"
      style={{ ['--color-compania' as string]: marca.color }}
    >
      <span className="marbete">{esVuelta ? 'Vuelta' : 'Ida'}</span>
      <span className="detalle">
        <span className="arriba">
          <strong>{fechaCorta(tren.fecha)}</strong>
          <span className="sello" style={{ background: marca.suave, color: marca.color }}>
            {marca.nombre}
          </span>
          <span
            className="sello destino"
            style={{ background: punta.suave, color: punta.color }}
          >
            {punta.nombre}
          </span>
        </span>
        <span className="abajo">
          {tren.salida} → {tren.llegada} · {duracion(tren.duracion_min)}
        </span>
      </span>
      <span className="importe">{euros(tren.precio)}</span>
    </a>
  )
}

/* --- Tarjeta de tren ------------------------------------------------------ */

/**
 * ¿Dice algo la tarifa sobre el billete?
 *
 * Las de Ouigo sí: una "Promo" no se cambia ni se devuelve, y eso pesa tanto
 * como el precio. Las demás fuentes rellenan el campo con su propio nombre o
 * con "Precio desde", que no informa de nada y solo ensucia la tarjeta.
 */
const TARIFAS_CON_CONDICIONES = new Set(['Promo', 'Básica'])

function tarifaUtil(tarifa: string | null): boolean {
  return tarifa != null && TARIFAS_CON_CONDICIONES.has(tarifa)
}

/** Cómo se escribe cada fuente cuando se le enseña al usuario. */
const NOMBRE_FUENTE: Record<string, string> = {
  edreams: 'eDreams',
  ouigo: 'Ouigo',
  renfe: 'Renfe',
  iryo: 'iryo',
}

function nombreFuente(fuente: string): string {
  return NOMBRE_FUENTE[fuente] ?? fuente
}

export function TarjetaTren({
  tren,
  destacado = false,
  motivo,
  rebajaPct,
  mostrarFecha = true,
}: {
  tren: Tren
  destacado?: boolean
  motivo?: string
  rebajaPct?: number | null
  /** Se oculta cuando la tarjeta ya va bajo una cabecera de día. */
  mostrarFecha?: boolean
}) {
  const marca = compania(tren.operador)
  const punta = destinoDelViaje(tren.origen_id, tren.destino_id)
  const esVuelta = tren.sentido === 'vuelta'
  const veredicto = valorar(useContext(ContextoReferencias), tren)

  return (
    <article
      className={`tren${destacado ? ' destacado' : ''}`}
      style={{ ['--color-compania' as string]: marca.color }}
    >
      {/* La dirección del viaje va arriba y a lo ancho: es lo primero que hay
          que saber, antes incluso que el precio. */}
      <div className={`rumbo ${esVuelta ? 'vuelta' : 'ida'}`}>
        <span className="marbete">{esVuelta ? 'Vuelta' : 'Ida'}</span>
        <span className="trayecto">
          {tren.origen} <span className="flecha">→</span> {tren.destino}
        </span>
      </div>

      <div className="fila-alta">
        <span className="sellos">
          <span className="sello" style={{ background: marca.suave, color: marca.color }}>
            {marca.nombre}
          </span>
          <span
            className="sello destino"
            style={{ background: punta.suave, color: punta.color }}
          >
            {punta.nombre}
            {punta.traslado > 0 && <em>+{punta.traslado} min</em>}
          </span>
        </span>
        <span className="precio" style={{ color: destacado ? 'var(--ahorro)' : undefined }}>
          {euros(tren.precio)}
          {rebajaPct != null && <span className="rebaja">−{Math.round(rebajaPct)}%</span>}
          {/* Responde a "¿lo cojo ya o espero?": compara con lo que ha costado
              este mismo viaje otros días. Solo aparece cuando hay histórico
              para opinar; si no, el hueco se queda vacío. */}
          {veredicto && (
            <span className={`juicio ${veredicto.tono}`} title={`Suele costar ${euros(veredicto.normal)}`}>
              {veredicto.etiqueta}
            </span>
          )}
        </span>
      </div>

      <div className="horario">
        <span className="hora">{tren.salida}</span>
        <span className="via">
          <span className="duracion">{duracion(tren.duracion_min)}</span>
          <span className="raya" />
        </span>
        <span className="hora">{tren.llegada}</span>
      </div>

      <div className="pie">
        {mostrarFecha && <span className="etiqueta">{fechaCorta(tren.fecha)}</span>}
        {tarifaUtil(tren.tarifa) && (
          <span
            className="etiqueta tarifa"
            title={
              tren.tarifa === 'Promo'
                ? 'La tarifa barata de Ouigo: no admite cambios ni devolución'
                : 'Tarifa estándar: admite cambios con condiciones'
            }
          >
            {tren.tarifa}
          </span>
        )}
        {tren.plazas != null && tren.plazas <= 10 && (
          <span className="etiqueta aviso">Quedan {tren.plazas}</span>
        )}
        <span style={{ marginLeft: 'auto' }}>precio visto en {tren.fuente}</span>
      </div>

      {motivo && <div className="motivo">{motivo}</div>}

      {/* Ninguna web permite enlazar a un billete concreto. La de eDreams al
          menos deja la búsqueda hecha (ruta y día puestos) y lo publica en
          url_busqueda; las demás solo abren su portada, y por eso se ofrece
          copiar los datos para pegarlos en su buscador. El botón dice a dónde
          lleva de verdad: poner aquí el nombre del operador haría creer que
          abre Renfe cuando abre eDreams. */}
      <div className="acciones">
        <BotonCopiar tren={tren} />
        <a
          className="boton principal"
          href={tren.url_busqueda || tren.url}
          target="_blank"
          rel="noreferrer"
          style={{ background: marca.color, borderColor: marca.color }}
        >
          {tren.url_busqueda
            ? `Ver en ${nombreFuente(tren.fuente)} ↗`
            : `Abrir ${marca.nombre} ↗`}
        </a>
      </div>
    </article>
  )
}

/** Copia los datos del viaje para pegarlos en el buscador del operador. */
function BotonCopiar({ tren }: { tren: Tren }) {
  const [copiado, setCopiado] = useState(false)

  const texto = [
    `${tren.origen} → ${tren.destino}`,
    fechaLarga(tren.fecha),
    `Salida ${tren.salida} · llegada ${tren.llegada}`,
    `${tren.operador} · ${euros(tren.precio)}`,
  ].join('\n')

  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    } catch {
      // Sin permiso de portapapeles (http, navegador antiguo): no pasa nada,
      // los datos están a la vista en la propia tarjeta.
    }
  }

  return (
    <button className="boton" onClick={copiar}>
      {copiado ? '✓ Copiado' : 'Copiar datos'}
    </button>
  )
}
