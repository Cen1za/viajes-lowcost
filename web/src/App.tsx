import { useMemo, useState } from 'react'
// (useState lo usan también los filtros plegables)
import { COMPANIAS, compania, companiasPresentes } from './companias'
import {
  CabeceraDia,
  Cargando,
  Chip,
  Iconos,
  ProgresoActualizacion,
  Seccion,
  TarjetaTren,
  Vacio,
} from './componentes'
import { agruparPorDia, desde, euros, fechaLarga, useDatos } from './datos'
import { destino } from './destinos'
import { useInstalacion } from './instalacion'
import {
  DIAS_SEMANA,
  FRANJAS,
  diasDelSentido,
  enDia,
  enFranja,
  horasFranja,
  usePreferencias,
} from './preferencias'
import type { Calendario, EstadoFuentes, Gangas, Latest, Tren } from './tipos'

type Vista = 'ofertas' | 'calendario' | 'trenes' | 'ajustes'
type Prefs = ReturnType<typeof usePreferencias>

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
        {vista === 'ofertas' && <VistaOfertas {...preferencias} />}
        {vista === 'calendario' && <VistaCalendario {...preferencias} />}
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

/* --- Filtros compartidos -------------------------------------------------- */

/**
 * Filtros en una sola línea.
 *
 * Solo se ve lo que más se toca —el sentido del viaje— y un botón que despliega
 * el resto. Tres filas de chips fijas comían un tercio de la pantalla del móvil
 * antes de enseñar un solo precio, que es justo lo que se viene a ver.
 */
function Filtros({
  prefs,
  cambiar,
  alternar,
  alternarDia,
  limpiar,
  companias,
  diasPresentes,
  conHorario = true,
}: Prefs & {
  companias: ReturnType<typeof companiasPresentes>
  diasPresentes: number[]
  conHorario?: boolean
}) {
  const [abierto, setAbierto] = useState(false)

  // Los días de viaje se configuran en Ajustes, no aquí: son una preferencia
  // estable (voy los viernes) y no algo que se toque en cada consulta.
  const activos =
    prefs.companias.length +
    prefs.franjas.length +
    (prefs.sentido !== 'todo' ? 1 : 0) +
    (prefs.soloDirectos ? 1 : 0)

  const hayMas = companias.length > 1 || conHorario

  return (
    <div className="filtros">
      <div className="chips linea">
        {(['todo', 'ida', 'vuelta'] as const).map((s) => (
          <Chip
            key={s}
            neutro
            activo={prefs.sentido === s}
            onClick={() => cambiar('sentido', s)}
          >
            {s === 'todo' ? 'Todo' : s === 'ida' ? 'Ida' : 'Vuelta'}
          </Chip>
        ))}

        {hayMas && (
          <button
            className={`chip mas${abierto ? ' abierto' : ''}`}
            aria-expanded={abierto}
            onClick={() => setAbierto((v) => !v)}
          >
            Filtros
            {activos > 0 && <span className="contador">{activos}</span>}
            <span className="punta" aria-hidden>
              ▾
            </span>
          </button>
        )}

        {activos > 0 && (
          <button className="chip limpiar" onClick={limpiar} aria-label="Quitar filtros">
            ✕
          </button>
        )}
      </div>

      {abierto && hayMas && (
        <div className="desplegable">
          {companias.length > 1 && (
            <div className="grupo-filtro">
              <span className="etiqueta-filtro">Compañía</span>
              <div className="opciones">
                {companias.map((c) => (
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
            </div>
          )}

          {conHorario && (
            <div className="grupo-filtro">
              <span className="etiqueta-filtro">Hora</span>
              <div className="opciones">
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
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Aplica todos los filtros del usuario. Genérico para no perder el tipo
 *  concreto (una Ganga es un Tren con motivo y porcentaje de bajada). */
function filtrar<T extends Tren>(trenes: T[], prefs: Prefs['prefs']): T[] {
  return trenes
    .filter((t) => prefs.sentido === 'todo' || t.sentido === prefs.sentido)
    .filter(
      (t) => !prefs.companias.length || prefs.companias.includes(compania(t.operador).id),
    )
    .filter((t) => enFranja(t.salida, prefs.franjas))
    // Los días se filtran por sentido: sales el viernes y vuelves el lunes.
    .filter((t) => enDia(t.fecha, diasDelSentido(prefs, t.sentido)))
    .filter(
      (t) =>
        !prefs.soloDirectos ||
        destino(t.sentido === 'vuelta' ? t.origen_id : t.destino_id).traslado === 0,
    )
}

function diasDe(trenes: { fecha: string }[]): number[] {
  const dias = new Set<number>()
  for (const t of trenes) {
    const [a, m, d] = t.fecha.split('-').map(Number)
    dias.add(new Date(a, m - 1, d).getDay())
  }
  return [...dias]
}

/* --- Ofertas -------------------------------------------------------------- */

function VistaOfertas(prefs: Prefs) {
  const { datos, error, cargando } = useDatos<Gangas>('gangas')

  const todas = datos?.ofertas ?? []
  const companias = useMemo(
    () => companiasPresentes(todas.map((o) => o.operador)),
    [todas],
  )
  const filtradas = useMemo(() => filtrar(todas, prefs.prefs), [todas, prefs.prefs])
  const porDia = useMemo(() => agruparPorDia(filtradas), [filtradas])

  if (cargando) return <Cargando />
  if (error || !datos)
    return (
      <Vacio icono="📡" titulo="No se han podido cargar los precios">
        {error ?? 'Inténtalo de nuevo en un momento.'}
      </Vacio>
    )

  if (!todas.length)
    return (
      <Vacio icono="🔍" titulo="Ninguna oferta destacada ahora mismo">
        Se revisan los precios cada hora. Cuando algo baje de forma llamativa
        aparecerá aquí y te llegará un aviso.
      </Vacio>
    )

  const sinHistorico = todas.every((o) => o.caida_pct == null)

  return (
    <>
      <ProgresoActualizacion actualizado={datos.actualizado} />
      <Filtros {...prefs} companias={companias} diasPresentes={diasDe(todas)} />

      <Seccion titulo={`${filtradas.length} ofertas en ${porDia.length} días`} />

      {sinHistorico && (
        <div className="nota">
          <strong>Todavía estamos aprendiendo.</strong> Hasta tener unos días de
          histórico se avisa de todo lo que baje de 25 €. Después se comparará
          con el precio habitual de cada viaje y solo saltarán las bajadas de
          verdad.
        </div>
      )}

      {porDia.length ? (
        porDia.map((grupo) => (
          <section key={grupo.fecha} className="grupo">
            <CabeceraDia
              fecha={grupo.fecha}
              minimo={grupo.minimo}
              cuantos={grupo.elementos.length}
            />
            <div className="lista">
              {grupo.elementos.map((o, i) => (
                <TarjetaTren
                  key={i}
                  tren={o}
                  destacado={o.caida_pct != null}
                  motivo={sinHistorico ? undefined : o.motivo}
                  rebajaPct={o.caida_pct}
                  mostrarFecha={false}
                />
              ))}
            </div>
          </section>
        ))
      ) : (
        <Vacio icono="🎚️" titulo="Ninguna oferta pasa los filtros">
          Prueba a quitar algún día, franja horaria o compañía.
        </Vacio>
      )}
    </>
  )
}

/* --- Calendario ----------------------------------------------------------- */

interface CasillaDia {
  ruta: string
  nombre: string
  sentido: string
  destinoId: string
  precio: number
  operador: string
  horario: string
}

function VistaCalendario(prefs: Prefs) {
  const { datos, error, cargando } = useDatos<Calendario>('calendario')

  /** Pivota ruta→fecha→precio a fecha→[rutas], que es como se mira un viaje. */
  const dias = useMemo(() => {
    if (!datos) return []
    const porFecha = new Map<string, CasillaDia[]>()

    for (const [ruta, fechas] of Object.entries(datos.rutas)) {
      const sentido = datos.sentidos?.[ruta] ?? 'ida'
      const [origenId, destinoId] = ruta.split('->')
      // El extremo que no es Madrid: en la vuelta está en el origen.
      const extremo = sentido === 'vuelta' ? origenId : destinoId
      for (const [fecha, precio] of Object.entries(fechas)) {
        const casilla: CasillaDia = {
          ruta,
          nombre: datos.nombres?.[ruta] ?? ruta,
          sentido,
          destinoId: extremo,
          precio,
          operador: datos.operadores?.[ruta]?.[fecha] ?? '',
          horario: datos.horarios?.[ruta]?.[fecha] ?? '',
        }
        const lista = porFecha.get(fecha)
        if (lista) lista.push(casilla)
        else porFecha.set(fecha, [casilla])
      }
    }

    return [...porFecha.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([fecha, casillas]) => ({
        fecha,
        casillas: casillas.sort((a, b) => a.precio - b.precio),
        minimo: Math.min(...casillas.map((c) => c.precio)),
      }))
  }, [datos])

  const visibles = dias
    .map((d) => ({
      ...d,
      casillas: d.casillas.filter(
        (c) =>
          (prefs.prefs.sentido === 'todo' || c.sentido === prefs.prefs.sentido) &&
          enDia(d.fecha, diasDelSentido(prefs.prefs, c.sentido)),
      ),
    }))
    .filter((d) => d.casillas.length)

  if (cargando) return <Cargando />
  if (error || !datos)
    return (
      <Vacio icono="📡" titulo="No se ha podido cargar el calendario">
        {error ?? 'Inténtalo de nuevo en un momento.'}
      </Vacio>
    )

  if (!dias.length)
    return (
      <Vacio icono="📅" titulo="Todavía no hay calendario">
        El barrido completo se hace de madrugada. Vuelve mañana o lánzalo a mano.
      </Vacio>
    )

  const barato = Math.min(...visibles.map((d) => d.minimo)) * 1.15

  return (
    <>
      <ProgresoActualizacion actualizado={datos.actualizado} />
      <Filtros
        {...prefs}
        companias={[]}
        diasPresentes={diasDe(dias)}
        conHorario={false}
      />
      <Seccion titulo={`${visibles.length} días con precio`} />

      {visibles.map((dia) => (
        <section
          key={dia.fecha}
          className={`dia-tarjeta${dia.minimo <= barato ? ' barato' : ''}`}
        >
          <div className="dia-tarjeta-alto">
            <span className="fecha">{fechaLarga(dia.fecha)}</span>
            <span className="minimo">{euros(dia.minimo)}</span>
          </div>
          {dia.casillas.map((c) => {
            const marca = compania(c.operador)
            const punta = destino(c.destinoId)
            return (
              <div key={c.ruta} className="dia-linea">
                <span className="flecha">{c.sentido === 'vuelta' ? '←' : '→'}</span>
                <span
                  className="sello destino"
                  style={{ background: punta.suave, color: punta.color }}
                >
                  {punta.nombre}
                  {punta.traslado > 0 && <em>+{punta.traslado} min</em>}
                </span>
                <span className="quien" style={{ color: marca.color }}>
                  {marca.nombre}
                </span>
                {c.horario && <span className="horas">{c.horario}</span>}
                <span className="importe">{euros(c.precio)}</span>
              </div>
            )
          })}
        </section>
      ))}

      {!visibles.length && (
        <Vacio icono="🎚️" titulo="Ningún día pasa los filtros">
          Prueba a quitar algún día de la semana o cambiar el sentido.
        </Vacio>
      )}
    </>
  )
}

/* --- Trenes --------------------------------------------------------------- */

function VistaTrenes(prefs: Prefs) {
  const { datos, error, cargando } = useDatos<Latest>('latest')

  const todos = datos?.trenes ?? []
  const companias = useMemo(
    () => companiasPresentes(todos.map((t) => t.operador)),
    [todos],
  )
  const filtrados = useMemo(() => filtrar(todos, prefs.prefs), [todos, prefs.prefs])
  // Sin recortes: si has filtrado por unos días o una franja, quieres ver
  // todos los billetes que quedan dentro, no una muestra.
  const porDia = useMemo(() => agruparPorDia(filtrados), [filtrados])

  if (cargando) return <Cargando />
  if (error || !datos)
    return (
      <Vacio icono="📡" titulo="No se han podido cargar los trenes">
        {error ?? 'Inténtalo de nuevo en un momento.'}
      </Vacio>
    )

  return (
    <>
      <ProgresoActualizacion actualizado={datos.actualizado} />
      <Filtros {...prefs} companias={companias} diasPresentes={diasDe(todos)} />

      <Seccion titulo={`${filtrados.length} trenes en ${porDia.length} días`} />

      {porDia.length ? (
        porDia.map((grupo) => (
          <section key={grupo.fecha} className="grupo">
            <CabeceraDia
              fecha={grupo.fecha}
              minimo={grupo.minimo}
              cuantos={grupo.elementos.length}
            />
            <div className="lista">
              {grupo.elementos.map((t, i) => (
                <TarjetaTren key={i} tren={t} mostrarFecha={false} />
              ))}
            </div>
          </section>
        ))
      ) : (
        <Vacio icono="🎚️" titulo="Ningún tren pasa los filtros">
          Prueba a quitar algún día, franja horaria o compañía.
        </Vacio>
      )}
    </>
  )
}

/* --- Instalación ---------------------------------------------------------- */

function PanelInstalacion() {
  const { estado, instalar, esApple } = useInstalacion()

  if (estado === 'instalada')
    return (
      <div className="panel">
        <h3>Ya está instalada ✓</h3>
        <p style={{ marginBottom: 0 }}>
          Estás usando la app instalada. Guarda los últimos precios, así que
          puedes consultarlos sin cobertura.
        </p>
      </div>
    )

  if (estado === 'disponible')
    return (
      <div className="panel">
        <h3>Instalar la app</h3>
        <p>
          Se abre a pantalla completa, arranca más rápido y guarda los últimos
          precios para verlos sin cobertura.
        </p>
        <button className="boton principal grande" onClick={instalar}>
          Instalar en este dispositivo
        </button>
      </div>
    )

  return (
    <div className="panel">
      <h3>Instalar la app</h3>
      <p style={{ marginBottom: 0 }}>
        {esApple ? (
          <>
            En iPhone: pulsa <strong>Compartir</strong> y luego{' '}
            <strong>Añadir a pantalla de inicio</strong>.
          </>
        ) : (
          <>
            Abre el menú <strong>⋮</strong> del navegador y elige{' '}
            <strong>Instalar aplicación</strong> o{' '}
            <strong>Añadir a pantalla de inicio</strong>. Si no lo ves, es que
            ya la tienes instalada.
          </>
        )}
      </p>
    </div>
  )
}

/* --- Ajustes -------------------------------------------------------------- */

function VistaAjustes({ prefs, cambiar, alternar, alternarDia, limpiar }: Prefs) {
  const { datos } = useDatos<EstadoFuentes>('estado_fuentes')
  const { datos: precios } = useDatos<Latest>('latest')

  // Días que el buscador está recopilando de verdad. Elegir uno que no esté
  // aquí no haría aparecer nada, así que conviene decirlo.
  const recopilados = useMemo(() => {
    const ida = new Set<number>()
    const vuelta = new Set<number>()
    for (const t of precios?.trenes ?? []) {
      const [a, m, d] = t.fecha.split('-').map(Number)
      ;(t.sentido === 'vuelta' ? vuelta : ida).add(new Date(a, m - 1, d).getDay())
    }
    return { ida, vuelta }
  }, [precios])

  return (
    <>
      <Seccion titulo="Días de viaje" />
      <div className="panel">
        <h3>¿Cuándo sueles ir y volver?</h3>
        <p>
          Por defecto, ida el viernes y vuelta el lunes. Los días en gris no se
          están buscando: para incluirlos hay que añadirlos también a{' '}
          <code>dias_ida</code> o <code>dias_vuelta</code> en{' '}
          <code>config/app.yaml</code>, porque si no, nunca llegan a consultarse.
        </p>

        {(
          [
            ['diasIda', 'Ida', 'Madrid → Elche/Alicante', recopilados.ida],
            ['diasVuelta', 'Vuelta', 'Elche/Alicante → Madrid', recopilados.vuelta],
          ] as const
        ).map(([campo, titulo, subtitulo, disponibles]) => (
          <div key={campo} className="bloque-dias">
            <div className="cabecera-dias">
              <strong>{titulo}</strong>
              <span>{subtitulo}</span>
            </div>
            <div className="opciones">
              {DIAS_SEMANA.map((d) => {
                const hay = disponibles.has(d.dia)
                return (
                  <button
                    key={d.dia}
                    className={`dia-boton${prefs[campo].includes(d.dia) ? ' activo' : ''}${
                      hay ? '' : ' vacio'
                    }`}
                    aria-pressed={prefs[campo].includes(d.dia)}
                    title={hay ? d.nombre : `${d.nombre} — no se está buscando`}
                    onClick={() => alternarDia(campo, d.dia)}
                  >
                    {d.corto}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <Seccion titulo="Tu horario preferido" />
      <div className="panel">
        <h3>¿A qué hora te gusta viajar?</h3>
        <p>
          Los trenes fuera de estas franjas dejan de aparecer en las listas. Si
          no eliges ninguna, se muestran todos.
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
              Oculta los trenes por Alicante, que obligan a 25 min más de traslado.
            </p>
          </span>
          <span className="palanca">
            <span />
          </span>
        </button>
      </div>

      <Seccion titulo="Compañías" />
      <div className="panel">
        <p>Cada tarjeta lleva el borde y el sello de quien vende el billete.</p>
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

      <Seccion titulo="Destinos" />
      <div className="panel">
        <p>
          El segundo sello dice a dónde llegas de verdad. Alicante suele salir
          más barato, pero deja 25 minutos de traslado hasta Elche.
        </p>
        <div className="leyenda">
          {['elche_av', 'alicante'].map((id) => {
            const d = destino(id)
            return (
              <div key={id} className="entrada">
                <span className="muestra" style={{ background: d.color }} />
                <span>
                  <span className="quien" style={{ color: d.color }}>
                    {d.nombre}
                  </span>
                  <br />
                  <span className="que">
                    {d.traslado
                      ? `${d.traslado} min extra hasta Elche`
                      : 'Sin traslados: la estación de Elche'}
                  </span>
                </span>
              </div>
            )
          })}
        </div>
      </div>

      <Seccion titulo="Estado de las webs" />
      <div className="panel">
        <p>
          De dónde salen los precios. Cada dato pasa un control de credibilidad
          antes de publicarse: si una web cambia y el lector empieza a sacar
          cifras raras, se descartan y la fuente se pone en rojo.
        </p>
        {datos?.fuentes.map((f) => (
          <div key={f.fuente} className="fuente">
            <span className={`luz ${f.ok ? 'ok' : 'ko'}`} />
            <span className="nombre">{f.fuente}</span>
            <span className="dato">
              {f.ofertas} precios · {f.duracion_s.toFixed(0)} s
              {f.descartadas > 0 && (
                <strong style={{ color: 'var(--error)' }}>
                  {' '}
                  · {f.descartadas} descartados
                </strong>
              )}
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
      <PanelInstalacion />

      <div className="panel">
        <button className="chip neutro" onClick={limpiar}>
          Restablecer todos los filtros
        </button>
      </div>
    </>
  )
}
