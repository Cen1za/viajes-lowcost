import { useEffect, useState, type ReactNode } from 'react'
import { compania } from './companias'
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
}: {
  fecha: string
  minimo: number
  cuantos: number
}) {
  return (
    <div className="dia-cabecera">
      <span className="titulo">{fechaLarga(fecha)}</span>
      <span className="resumen">
        {cuantos} {cuantos === 1 ? 'tren' : 'trenes'} · desde{' '}
        <strong>{euros(minimo)}</strong>
      </span>
    </div>
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

/* --- Tarjeta de tren ------------------------------------------------------ */

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
        {tren.plazas != null && tren.plazas <= 10 && (
          <span className="etiqueta aviso">Quedan {tren.plazas}</span>
        )}
        <span style={{ marginLeft: 'auto' }}>precio visto en {tren.fuente}</span>
      </div>

      {motivo && <div className="motivo">{motivo}</div>}

      {/* Ninguna web de tren permite enlazar a un billete concreto, así que en
          vez de fingirlo se abre la del operador y se ofrece copiar los datos
          para pegarlos en su buscador. */}
      <div className="acciones">
        <BotonCopiar tren={tren} />
        <a
          className="boton principal"
          href={tren.url}
          target="_blank"
          rel="noreferrer"
          style={{ background: marca.color, borderColor: marca.color }}
        >
          Abrir {marca.nombre} ↗
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
