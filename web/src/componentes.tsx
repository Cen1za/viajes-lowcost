import type { ReactNode } from 'react'
import { compania } from './companias'
import { duracion, euros, fechaCorta } from './datos'
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
}

/* --- Piezas sueltas ------------------------------------------------------- */

export function Seccion({ titulo, apunte }: { titulo: string; apunte?: ReactNode }) {
  return (
    <div className="seccion">
      <h2>{titulo}</h2>
      {apunte && <span className="apunte">{apunte}</span>}
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
  traslado = 0,
  destacado = false,
  motivo,
  rebajaPct,
}: {
  tren: Tren
  traslado?: number
  destacado?: boolean
  motivo?: string
  rebajaPct?: number | null
}) {
  const marca = compania(tren.operador)

  return (
    <a
      className={`tren${destacado ? ' destacado' : ''}`}
      href={tren.url}
      target="_blank"
      rel="noreferrer"
      style={{ ['--color-compania' as string]: marca.color }}
    >
      <div className="fila-alta">
        <span
          className="sello"
          style={{ background: marca.suave, color: marca.color }}
        >
          {marca.nombre}
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

      <div className="estaciones">
        <span>{tren.origen}</span>
        <span>{tren.destino}</span>
      </div>

      <div className="pie">
        <span className="etiqueta">
          {tren.sentido === 'vuelta' ? '← Vuelta' : '→ Ida'}
        </span>
        <span className="etiqueta">{fechaCorta(tren.fecha)}</span>
        {traslado > 0 && (
          <span className="etiqueta aviso">
            {/* En la vuelta el traslado se hace ANTES de coger el tren. */}
            +{traslado} min {tren.sentido === 'vuelta' ? 'desde' : 'hasta'} Elche
          </span>
        )}
        {tren.plazas != null && tren.plazas <= 10 && (
          <span className="etiqueta aviso">Quedan {tren.plazas}</span>
        )}
        <span style={{ marginLeft: 'auto' }}>vía {tren.fuente}</span>
      </div>

      {motivo && <div className="motivo">{motivo}</div>}
    </a>
  )
}
