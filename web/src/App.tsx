import { useMemo, useState } from 'react'
import { desde, duracion, euros, fechaCorta, useDatos } from './datos'
import type { Calendario, EstadoFuentes, Gangas, Latest, Tren } from './tipos'

type Vista = 'ofertas' | 'calendario' | 'trenes' | 'fuentes'

export default function App() {
  const [vista, setVista] = useState<Vista>('ofertas')

  return (
    <div className="app">
      <header>
        <h1>Madrid → Elche</h1>
        <p>Los precios más bajos, de todas las webs a la vez.</p>
      </header>

      <nav>
        {(
          [
            ['ofertas', 'Ofertas'],
            ['calendario', 'Calendario'],
            ['trenes', 'Trenes'],
            ['fuentes', 'Fuentes'],
          ] as [Vista, string][]
        ).map(([id, etiqueta]) => (
          <button
            key={id}
            className={vista === id ? 'activo' : ''}
            onClick={() => setVista(id)}
          >
            {etiqueta}
          </button>
        ))}
      </nav>

      <main>
        {vista === 'ofertas' && <VistaOfertas />}
        {vista === 'calendario' && <VistaCalendario />}
        {vista === 'trenes' && <VistaTrenes />}
        {vista === 'fuentes' && <VistaFuentes />}
      </main>
    </div>
  )
}

function Estado({ cargando, error }: { cargando: boolean; error: string | null }) {
  if (cargando) return <p className="aviso">Cargando…</p>
  if (error) return <p className="aviso error">{error}</p>
  return null
}

function VistaOfertas() {
  const { datos, error, cargando } = useDatos<Gangas>('gangas')
  if (!datos) return <Estado cargando={cargando} error={error} />

  if (!datos.ofertas.length) {
    return (
      <p className="aviso">
        Ahora mismo no hay ninguna oferta destacada. Seguimos vigilando cada 4 horas.
      </p>
    )
  }

  return (
    <>
      <p className="marca">Actualizado {desde(datos.actualizado)}</p>
      {datos.ofertas.map((o, i) => (
        <a key={i} className="tarjeta destacada" href={o.url} target="_blank" rel="noreferrer">
          <div className="fila">
            <span className="precio">{euros(o.precio)}</span>
            {o.caida_pct != null && <span className="caida">−{Math.round(o.caida_pct)}%</span>}
          </div>
          <div className="ruta">
            {o.origen} → {o.destino}
          </div>
          <div className="detalle">
            {fechaCorta(o.fecha)} · {o.salida}–{o.llegada} ({duracion(o.duracion_min)}) ·{' '}
            {o.operador}
          </div>
          <div className="motivo">{o.motivo}</div>
        </a>
      ))}
    </>
  )
}

function VistaCalendario() {
  const { datos, error, cargando } = useDatos<Calendario>('calendario')
  if (!datos) return <Estado cargando={cargando} error={error} />

  const rutas = Object.entries(datos.rutas)
  if (!rutas.length) return <p className="aviso">Todavía no hay datos de calendario.</p>

  return (
    <>
      <p className="marca">Actualizado {desde(datos.actualizado)}</p>
      {rutas.map(([ruta, dias]) => (
        <MapaRuta
          key={ruta}
          titulo={datos.nombres?.[ruta] ?? ruta.replace('->', ' → ').replace(/_/g, ' ')}
          dias={dias}
        />
      ))}
    </>
  )
}

function MapaRuta({ titulo, dias }: { titulo: string; dias: Record<string, number> }) {
  const entradas = Object.entries(dias).sort()
  const precios = entradas.map(([, p]) => p)
  const min = Math.min(...precios)
  const max = Math.max(...precios)

  /** 0 = el más barato del rango, 1 = el más caro. */
  const intensidad = (precio: number) => (max === min ? 0 : (precio - min) / (max - min))

  return (
    <section className="mapa">
      <h2>{titulo}</h2>
      <div className="rejilla">
        {entradas.map(([dia, precio]) => (
          <div
            key={dia}
            className="celda"
            style={{
              // Verde para lo barato, ámbar para lo caro.
              background: `hsl(${145 - intensidad(precio) * 110} 65% ${
                22 + intensidad(precio) * 12
              }%)`,
            }}
          >
            <span className="dia">{fechaCorta(dia)}</span>
            <span className="valor">{Math.round(precio)}€</span>
          </div>
        ))}
      </div>
      <p className="leyenda">
        Más barato {euros(min)} · más caro {euros(max)}
      </p>
    </section>
  )
}

function VistaTrenes() {
  const { datos, error, cargando } = useDatos<Latest>('latest')
  const [soloDirectos, setSoloDirectos] = useState(false)

  const trenes = useMemo(() => {
    if (!datos) return []
    const lista = soloDirectos
      ? datos.trenes.filter((t) => (datos.traslado_min[t.destino_id] ?? 0) === 0)
      : datos.trenes
    return [...lista].sort((a, b) => a.precio - b.precio).slice(0, 60)
  }, [datos, soloDirectos])

  if (!datos) return <Estado cargando={cargando} error={error} />

  return (
    <>
      <p className="marca">Actualizado {desde(datos.actualizado)}</p>
      <label className="filtro">
        <input
          type="checkbox"
          checked={soloDirectos}
          onChange={(e) => setSoloDirectos(e.target.checked)}
        />
        Solo Elche AV (sin traslado desde Alicante)
      </label>
      {trenes.map((t, i) => (
        <FilaTren key={i} tren={t} traslado={datos.traslado_min[t.destino_id] ?? 0} />
      ))}
      {!trenes.length && <p className="aviso">Sin trenes que mostrar.</p>}
    </>
  )
}

function FilaTren({ tren, traslado }: { tren: Tren; traslado: number }) {
  return (
    <a className="tarjeta" href={tren.url} target="_blank" rel="noreferrer">
      <div className="fila">
        <span className="precio">{euros(tren.precio)}</span>
        <span className="operador">{tren.operador}</span>
      </div>
      <div className="ruta">
        {tren.origen} → {tren.destino}
        {traslado > 0 && <span className="traslado">+{traslado} min hasta Elche</span>}
      </div>
      <div className="detalle">
        {fechaCorta(tren.fecha)} · {tren.salida}–{tren.llegada} ({duracion(tren.duracion_min)}) ·
        vía {tren.fuente}
        {tren.plazas != null && ` · ${tren.plazas} plazas`}
      </div>
    </a>
  )
}

function VistaFuentes() {
  const { datos, error, cargando } = useDatos<EstadoFuentes>('estado_fuentes')
  if (!datos) return <Estado cargando={cargando} error={error} />

  return (
    <>
      <p className="marca">Última comprobación {desde(datos.actualizado)}</p>
      {datos.fuentes.map((f) => (
        <div key={f.fuente} className={`tarjeta fuente ${f.ok ? 'ok' : 'ko'}`}>
          <div className="fila">
            <span className="operador">{f.fuente}</span>
            <span>{f.ok ? 'funcionando' : 'con problemas'}</span>
          </div>
          <div className="detalle">
            {f.ofertas} precios en {f.duracion_s.toFixed(1)} s
          </div>
          {f.error && <div className="motivo">{f.error}</div>}
        </div>
      ))}
    </>
  )
}
