import { useMemo, useState } from 'react'
import { COMPANIAS, compania, companiasPresentes } from './companias'
import { Cargando, Chip, Iconos, Seccion, TarjetaTren, Vacio } from './componentes'
import { desde, euros, fechaCorta, useDatos } from './datos'
import {
  FRANJAS,
  enFranja,
  horasFranja,
  usePreferencias,
  type Preferencias,
} from './preferencias'
import type { Calendario, EstadoFuentes, Gangas, Latest, Tren } from './tipos'

type Vista = 'ofertas' | 'calendario' | 'trenes' | 'ajustes'

const PESTANAS: { id: Vista; nombre: string; icono: JSX.Element }[] = [
  { id: 'ofertas', nombre: 'Ofertas', icono: Iconos.ofertas },
  { id: 'calendario', nombre: 'Calendario', icono: Iconos.calendario },
  { id: 'trenes', nombre: 'Trenes', icono: Iconos.trenes },
  { id: 'ajustes', nombre: 'Ajustes', icono: Iconos.ajustes },
]

export default function App() {
  const [vista, setVista] = useState<Vista>('ofertas')
  const preferencias = usePreferencias()

  return (
    <div className="app">
      <header className="cabecera">
        <h1>
          <span aria-hidden>🚄</span> Madrid ⇄ Elche
        </h1>
        <p className="sub">El precio más bajo de todas las webs, en un sitio.</p>
      </header>

      <main>
        {vista === 'ofertas' && <VistaOfertas />}
        {vista === 'calendario' && <VistaCalendario prefs={preferencias.prefs} />}
        {vista === 'trenes' && <VistaTrenes {...preferencias} />}
        {vista === 'ajustes' && <VistaAjustes {...preferencias} />}
      </main>

      <nav className="barra">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            className={vista === p.id ? 'activo' : ''}
            aria-current={vista === p.id ? 'page' : undefined}
            onClick={() => setVista(p.id)}
          >
            {p.icono}
            {p.nombre}
          </button>
        ))}
      </nav>
    </div>
  )
}

/* --- Ofertas -------------------------------------------------------------- */

function VistaOfertas() {
  const { datos, error, cargando } = useDatos<Gangas>('gangas')

  if (cargando) return <Cargando />
  if (error || !datos)
    return (
      <Vacio icono="📡" titulo="No se han podido cargar los precios">
        {error ?? 'Inténtalo de nuevo en un momento.'}
      </Vacio>
    )

  if (!datos.ofertas.length)
    return (
      <Vacio icono="🔍" titulo="Ninguna oferta destacada ahora mismo">
        Se revisan los precios cada hora. Cuando algo baje de forma llamativa
        aparecerá aquí y te llegará un aviso.
      </Vacio>
    )

  // Mientras no haya histórico, todas las ofertas comparten el mismo motivo.
  // Repetirlo en cada tarjeta es ruido: se dice una vez y ya.
  const sinHistorico = datos.ofertas.every((o) => o.caida_pct == null)

  return (
    <>
      <Seccion
        titulo={`${datos.ofertas.length} ofertas destacadas`}
        apunte={desde(datos.actualizado)}
      />

      {sinHistorico && (
        <div className="nota">
          <strong>Todavía estamos aprendiendo.</strong> Hasta tener unos días de
          histórico se avisa de todo lo que baje de 25 €. Después se comparará
          con el precio habitual de cada viaje y solo saltarán las bajadas de
          verdad.
        </div>
      )}

      <div className="lista">
        {datos.ofertas.map((o, i) => (
          <TarjetaTren
            key={i}
            tren={o}
            traslado={
              datos.traslado_min?.[
                o.sentido === 'vuelta' ? o.origen_id : o.destino_id
              ] ?? 0
            }
            destacado={o.caida_pct != null}
            motivo={sinHistorico ? undefined : o.motivo}
            rebajaPct={o.caida_pct}
          />
        ))}
      </div>
    </>
  )
}

/* --- Calendario ----------------------------------------------------------- */

function VistaCalendario({ prefs }: { prefs: Preferencias }) {
  const { datos, error, cargando } = useDatos<Calendario>('calendario')

  if (cargando) return <Cargando />
  if (error || !datos)
    return (
      <Vacio icono="📡" titulo="No se ha podido cargar el calendario">
        {error ?? 'Inténtalo de nuevo en un momento.'}
      </Vacio>
    )

  const rutas = Object.entries(datos.rutas).filter(
    ([ruta]) =>
      prefs.sentido === 'todo' || (datos.sentidos?.[ruta] ?? 'ida') === prefs.sentido,
  )

  if (!rutas.length)
    return (
      <Vacio icono="📅" titulo="Todavía no hay calendario">
        El barrido completo se hace de madrugada. Vuelve mañana o lánzalo a mano.
      </Vacio>
    )

  // Ida primero, vuelta después: es el orden en que se piensa un viaje.
  const ordenadas = rutas.sort(([a], [b]) => {
    const sa = datos.sentidos?.[a] === 'vuelta' ? 1 : 0
    const sb = datos.sentidos?.[b] === 'vuelta' ? 1 : 0
    return sa - sb || a.localeCompare(b)
  })

  return (
    <>
      <Seccion titulo="Precio más bajo por día" apunte={desde(datos.actualizado)} />
      {ordenadas.map(([ruta, dias]) => (
        <MapaRuta
          key={ruta}
          titulo={datos.nombres?.[ruta] ?? ruta.replace('->', ' → ')}
          sentido={datos.sentidos?.[ruta] ?? 'ida'}
          dias={dias}
          operadores={datos.operadores?.[ruta] ?? {}}
        />
      ))}
    </>
  )
}

function MapaRuta({
  titulo,
  sentido,
  dias,
  operadores,
}: {
  titulo: string
  sentido: string
  dias: Record<string, number>
  operadores: Record<string, string>
}) {
  const entradas = Object.entries(dias).sort()
  if (!entradas.length) return null

  const precios = entradas.map(([, p]) => p)
  const min = Math.min(...precios)
  // "Barato" = dentro de un 15% del mínimo del rango. Un umbral relativo
  // funciona igual de bien en un mes caro que en uno barato.
  const corte = min * 1.15

  return (
    <section style={{ marginBottom: 22 }}>
      <Seccion
        titulo={`${sentido === 'vuelta' ? 'Vuelta' : 'Ida'} · ${titulo}`}
        apunte={`desde ${euros(min)}`}
      />
      <div className="rejilla">
        {entradas.map(([dia, precio]) => {
          const marca = compania(operadores[dia] ?? '')
          return (
            <div
              key={dia}
              className={`dia${precio <= corte ? ' barato' : ''}`}
              style={{ ['--color-compania' as string]: marca.color }}
            >
              <span className="fecha">{fechaCorta(dia)}</span>
              <span className="importe">{Math.round(precio)}€</span>
              <span className="quien" style={{ color: marca.color }}>
                {marca.nombre}
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

/* --- Trenes --------------------------------------------------------------- */

function VistaTrenes({
  prefs,
  cambiar,
  alternar,
  limpiar,
}: ReturnType<typeof usePreferencias>) {
  const { datos, error, cargando } = useDatos<Latest>('latest')

  const disponibles = useMemo(
    () => companiasPresentes((datos?.trenes ?? []).map((t) => t.operador)),
    [datos],
  )

  /** Minutos de traslado del extremo que no es Madrid. */
  const traslado = (t: Tren) =>
    (datos?.traslado_min[t.sentido === 'vuelta' ? t.origen_id : t.destino_id] ?? 0)

  const filtrados = useMemo(() => {
    if (!datos) return []
    return datos.trenes
      .filter((t) => prefs.sentido === 'todo' || t.sentido === prefs.sentido)
      .filter((t) => !prefs.companias.length || prefs.companias.includes(compania(t.operador).id))
      .filter((t) => enFranja(t.salida, prefs.franjas))
      .filter(
        (t) =>
          !prefs.soloDirectos ||
          (datos.traslado_min[t.sentido === 'vuelta' ? t.origen_id : t.destino_id] ?? 0) === 0,
      )
      .sort((a, b) => a.precio - b.precio)
  }, [datos, prefs])

  const trenes = filtrados.slice(0, 60)

  if (cargando) return <Cargando />
  if (error || !datos)
    return (
      <Vacio icono="📡" titulo="No se han podido cargar los trenes">
        {error ?? 'Inténtalo de nuevo en un momento.'}
      </Vacio>
    )

  const hayFiltros =
    prefs.companias.length > 0 ||
    prefs.franjas.length > 0 ||
    prefs.sentido !== 'todo' ||
    prefs.soloDirectos

  return (
    <>
      {/* Sentido y compañía comparten fila: son las dos decisiones que
          más se tocan y así se ven de un vistazo sin scroll vertical. */}
      <div className="chips">
        {(['todo', 'ida', 'vuelta'] as const).map((s) => (
          <Chip
            key={s}
            neutro
            activo={prefs.sentido === s}
            onClick={() => cambiar('sentido', s)}
          >
            {s === 'todo' ? 'Todo' : s === 'ida' ? '→ Ida' : '← Vuelta'}
          </Chip>
        ))}
        <span className="separador" />
        {disponibles.map((c) => (
          <Chip
            key={c.id}
            activo={prefs.companias.includes(c.id)}
            color={c.color}
            onClick={() => alternar('companias', c.id)}
          >
            {c.nombre}
          </Chip>
        ))}
      </div>

      <div className="chips">
        {FRANJAS.map((f) => (
          <Chip
            key={f.id}
            neutro
            activo={prefs.franjas.includes(f.id)}
            onClick={() => alternar('franjas', f.id)}
          >
            {f.nombre}
          </Chip>
        ))}
        {hayFiltros && (
          <Chip neutro activo={false} onClick={limpiar}>
            ✕ Quitar filtros
          </Chip>
        )}
      </div>

      <Seccion
        titulo={
          filtrados.length > trenes.length
            ? `${trenes.length} de ${filtrados.length} trenes`
            : `${trenes.length} trenes`
        }
        apunte={hayFiltros ? 'filtrados' : desde(datos.actualizado)}
      />

      {trenes.length ? (
        <div className="lista">
          {trenes.map((t, i) => (
            <TarjetaTren key={i} tren={t} traslado={traslado(t)} />
          ))}
        </div>
      ) : (
        <Vacio icono="🎚️" titulo="Ningún tren pasa los filtros">
          Prueba a quitar alguna franja horaria o compañía en los botones de arriba.
        </Vacio>
      )}
    </>
  )
}

/* --- Ajustes -------------------------------------------------------------- */

function VistaAjustes({
  prefs,
  cambiar,
  alternar,
  limpiar,
}: ReturnType<typeof usePreferencias>) {
  const { datos } = useDatos<EstadoFuentes>('estado_fuentes')

  return (
    <>
      <Seccion titulo="Tu horario preferido" />
      <div className="panel">
        <h3>¿A qué hora te gusta viajar?</h3>
        <p>
          Los trenes fuera de estas franjas dejan de aparecer en la lista. Si no
          eliges ninguna, se muestran todos.
        </p>
        <div className="opciones">
          {FRANJAS.map((f) => (
            <Chip
              key={f.id}
              neutro
              activo={prefs.franjas.includes(f.id)}
              onClick={() => alternar('franjas', f.id)}
            >
              {f.nombre}{' '}
              <span style={{ opacity: 0.6, fontWeight: 500 }}>{horasFranja(f)}</span>
            </Chip>
          ))}
        </div>
      </div>

      <div className="panel">
        <button
          className="interruptor"
          aria-pressed={prefs.soloDirectos}
          onClick={() => cambiar('soloDirectos', !prefs.soloDirectos)}
        >
          <span>
            <h3>Solo Elche AV</h3>
            <p style={{ margin: 0 }}>
              Oculta los trenes a Alicante, que obligan a 25 min más de traslado.
            </p>
          </span>
          <span className="palanca">
            <span />
          </span>
        </button>
      </div>

      <Seccion titulo="Compañías" />
      <div className="panel">
        <p>
          Cada tarjeta lleva el color de quien vende el billete. Toca una para
          filtrar por ella en la pestaña de trenes.
        </p>
        <div className="leyenda">
          {COMPANIAS.map((c) => (
            <div key={c.id} className="entrada">
              <span className="muestra" style={{ background: c.color }} />
              <span>
                <span className="quien" style={{ color: c.color }}>
                  {c.nombre}
                </span>
                <br />
                <span className="que">{c.descripcion}</span>
              </span>
              <button
                className="chip"
                style={{ marginLeft: 'auto' }}
                aria-pressed={prefs.companias.includes(c.id)}
                onClick={() => alternar('companias', c.id)}
              >
                {prefs.companias.includes(c.id) ? 'Filtrando' : 'Filtrar'}
              </button>
            </div>
          ))}
        </div>
      </div>

      <Seccion titulo="Estado de las webs" />
      <div className="panel">
        <p>
          De dónde salen los precios. Si alguna falla, las demás siguen
          funcionando.
        </p>
        {datos?.fuentes.map((f) => (
          <div key={f.fuente} className="fuente">
            <span className={`luz ${f.ok ? 'ok' : 'ko'}`} />
            <span className="nombre">{f.fuente}</span>
            <span className="dato">
              {f.ofertas} precios · {f.duracion_s.toFixed(0)} s
            </span>
          </div>
        ))}
        {datos && (
          <p style={{ margin: '12px 0 0' }}>
            Última comprobación {desde(datos.actualizado)}.
          </p>
        )}
      </div>

      <Seccion titulo="Instalar en el móvil" />
      <div className="panel">
        <p style={{ marginBottom: 0 }}>
          En Chrome, menú <strong>⋮ → Añadir a pantalla de inicio</strong>. En
          iPhone, <strong>Compartir → Añadir a pantalla de inicio</strong>. Se
          abre a pantalla completa y guarda los últimos precios para poder
          consultarlos sin cobertura.
        </p>
      </div>

      <div className="panel">
        <button className="chip neutro" onClick={limpiar}>
          Restablecer todos los filtros
        </button>
      </div>
    </>
  )
}
