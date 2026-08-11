import { useMemo, useState, type ReactNode } from 'react'
// (useState lo usan también los filtros plegables)
import { COMPANIAS, compania, companiasPresentes } from './companias'
import {
  BotonActualizar,
  CabeceraDia,
  CabeceraFinde,
  Cargando,
  Chip,
  Iconos,
  ProgresoActualizacion,
  ProveedorReferencias,
  Seccion,
  TarjetaPlan,
  TarjetaTren,
  Vacio,
} from './componentes'
import {
  agruparPorDia,
  agruparPorFinde,
  desde,
  euros,
  fechaLarga,
  useDatos,
} from './datos'
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
import { activarAvisos, estadoAvisos } from './avisos'
import { loQueFalta } from './referencias'
import type {
  Calendario,
  EstadoFuentes,
  Gangas,
  Latest,
  Promociones,
  Referencias,
  Tren,
} from './tipos'

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
  // Se carga una vez arriba y viaja por contexto: lo usan las tarjetas de
  // cuatro vistas distintas para decir si un billete está barato.
  const { datos: referencias } = useDatos<Referencias>('referencias')

  return (
    <ProveedorReferencias datos={referencias}>
    <div className="app">
      <header className="cabecera">
        <div className="titulo-app">
          <h1>
            <span aria-hidden>🚄</span> Madrid ⇄ Elche
          </h1>
          <BotonInstalar />
          <BotonActualizar />
        </div>
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
    </ProveedorReferencias>
  )
}

/**
 * Explica por qué las tarjetas todavía no dicen si un billete está barato.
 *
 * Callar sin más haría pensar que la función no existe. Como el dato tarda
 * días en reunirse, se enseña cuánto falta y desaparece solo al llegar.
 */
function ReuniendoPrecios() {
  const { datos } = useDatos<Referencias>('referencias')
  const falta = loQueFalta(datos)
  if (!falta || !datos) return null

  const hechos = Math.min(datos.dias_reunidos, datos.dias_necesarios)
  const porcentaje = Math.round((hechos / datos.dias_necesarios) * 100)

  return (
    <div className="reuniendo">
      {/* Ojo con el nombre: "barra" ya es la navegación inferior, que va
          fija a la pantalla, y esta heredaba su position:fixed. */}
      <span className="medidor" aria-hidden>
        <span style={{ width: `${porcentaje}%` }} />
      </span>
      <span>
        {falta} Llevo {hechos} de {datos.dias_necesarios}.
      </span>
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
  conMejorPrecio = false,
}: Prefs & {
  companias: ReturnType<typeof companiasPresentes>
  diasPresentes: number[]
  conHorario?: boolean
  /** El botón solo aparece donde hay una lista que resumir. */
  conMejorPrecio?: boolean
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
  const enPlan = conMejorPrecio && prefs.mejorPrecio

  return (
    <div className="filtros">
      <div className="chips linea">
        {conMejorPrecio && (
          <button
            className="chip mejor"
            aria-pressed={prefs.mejorPrecio}
            onClick={() => cambiar('mejorPrecio', !prefs.mejorPrecio)}
          >
            {Iconos.ofertas}
            Mejor precio
          </button>
        )}

        {/* En modo plan cada finde ya lleva su ida y su vuelta: elegir sentido
            no querría decir nada. */}
        {!enPlan &&
          (['todo', 'ida', 'vuelta'] as const).map((s) => (
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

/**
 * Pantalla principal: todos los precios, ordenados por finde.
 *
 * Antes solo enseñaba las gangas, y con una sola ganga la app parecía vacía
 * aunque hubiera cientos de precios recogidos. Ahora las gangas se destacan
 * arriba y debajo va todo, agrupado por el finde al que corresponde cada
 * viaje: es la unidad en la que se decide ir o no ir.
 */
function VistaOfertas(prefs: Prefs) {
  const { datos, error, cargando } = useDatos<Latest>('latest')
  const { datos: gangas } = useDatos<Gangas>('gangas')

  const todos = datos?.trenes ?? []
  const companias = useMemo(
    () => companiasPresentes(todos.map((t) => t.operador)),
    [todos],
  )
  const filtrados = useMemo(() => filtrar(todos, prefs.prefs), [todos, prefs.prefs])
  const findes = useMemo(() => agruparPorFinde(filtrados), [filtrados])

  // En modo plan hacen falta los dos sentidos aunque el chip diga otra cosa:
  // un finde sin vuelta no es un viaje.
  const planes = useMemo(() => {
    if (!prefs.prefs.mejorPrecio) return []
    const ambos = filtrar(todos, { ...prefs.prefs, sentido: 'todo' })
    return agruparPorFinde(ambos).map((finde) => {
      const trenes = finde.dias.flatMap((d) => d.elementos)
      const barato = (sentido: string) =>
        trenes
          .filter((t) => (t.sentido === 'vuelta') === (sentido === 'vuelta'))
          .sort((a, b) => a.precio - b.precio)[0]
      return { finde, ida: barato('ida'), vuelta: barato('vuelta') }
    })
  }, [todos, prefs.prefs])

  // Las gangas siguen mandando: son el motivo de que exista la app. Van
  // arriba, con su motivo, y aparte de la lista completa.
  const destacadas = useMemo(
    () => filtrar(gangas?.ofertas ?? [], prefs.prefs),
    [gangas, prefs.prefs],
  )
  const sinHistorico = destacadas.every((o) => o.caida_pct == null)

  if (cargando) return <Cargando />
  if (error || !datos)
    return (
      <Vacio icono="📡" titulo="No se han podido cargar los precios">
        {error ?? 'Inténtalo de nuevo en un momento.'}
      </Vacio>
    )

  if (!todos.length)
    return (
      <Vacio icono="🔍" titulo="Todavía no hay precios recogidos">
        Se revisan los precios cada hora. En cuanto entre la primera búsqueda
        aparecerán aquí.
      </Vacio>
    )

  return (
    <>
      <ProgresoActualizacion actualizado={datos.actualizado} />
      <ReuniendoPrecios />
      <Filtros
        {...prefs}
        companias={companias}
        diasPresentes={diasDe(todos)}
        conMejorPrecio
      />

      {prefs.prefs.mejorPrecio ? (
        <>
          <Seccion titulo="Mejor precio por finde" apunte={diasDelPlan(prefs.prefs)} />
          {planes.length ? (
            planes.map(({ finde, ida, vuelta }) => (
              <section key={finde.desde} className="grupo">
                <CabeceraFinde {...finde} />
                <TarjetaPlan ida={ida} vuelta={vuelta} />
              </section>
            ))
          ) : (
            <Vacio icono="🎚️" titulo="Ningún finde pasa los filtros">
              Cambia los días o el horario en Ajustes, que es de donde salen.
            </Vacio>
          )}
        </>
      ) : (
        <ListaCompleta
          destacadas={destacadas}
          sinHistorico={sinHistorico}
          filtrados={filtrados}
          findes={findes}
        />
      )}
    </>
  )
}

/** Los días que está usando el plan, para recordar de dónde salen. */
function diasDelPlan(prefs: Prefs['prefs']): string {
  const nombres = (dias: number[]) =>
    dias.length
      ? dias.map((d) => DIAS_SEMANA.find((s) => s.dia === d)?.corto).join('')
      : 'todos'
  return `ida ${nombres(prefs.diasIda)} · vuelta ${nombres(prefs.diasVuelta)}`
}

function ListaCompleta({
  destacadas,
  sinHistorico,
  filtrados,
  findes,
}: {
  destacadas: Gangas['ofertas']
  sinHistorico: boolean
  filtrados: Tren[]
  findes: ReturnType<typeof agruparPorFinde<Tren>>
}) {
  return (
    <>
      {destacadas.length > 0 && (
        <>
          <Seccion
            titulo={destacadas.length === 1 ? 'Chollo del momento' : 'Chollos del momento'}
            apunte={sinHistorico ? 'por debajo de 25 €' : 'muy por debajo de lo normal'}
          />
          <div className="lista">
            {destacadas.map((o, i) => (
              <TarjetaTren
                key={i}
                tren={o}
                destacado
                motivo={sinHistorico ? undefined : o.motivo}
                rebajaPct={o.caida_pct}
              />
            ))}
          </div>
        </>
      )}

      <Seccion
        titulo={`Todos los precios · ${filtrados.length}`}
        apunte={`${findes.length} ${findes.length === 1 ? 'finde' : 'findes'}`}
      />

      {findes.length ? (
        findes.map((finde) => (
          <section key={finde.desde} className="grupo">
            <CabeceraFinde {...finde} />
            {finde.dias.map((dia) => (
              <div key={dia.fecha} className="dentro-del-finde">
                <CabeceraDia
                  fecha={dia.fecha}
                  minimo={dia.minimo}
                  cuantos={dia.elementos.length}
                  trenes={dia.elementos}
                />
                <div className="lista">
                  {dia.elementos.map((t, i) => (
                    <TarjetaTren key={i} tren={t} mostrarFecha={false} />
                  ))}
                </div>
              </div>
            ))}
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
              trenes={grupo.elementos}
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

/**
 * Avisos como notificación del móvil.
 *
 * El paso raro -copiar un texto y pegarlo en GitHub- es el precio de no tener
 * servidor: quien manda las notificaciones es el propio GitHub Actions, y para
 * eso necesita saber a qué dispositivo. Se explica en vez de disimularlo.
 */
function PanelAvisos() {
  const [estado, setEstado] = useState(estadoAvisos)
  const [suscripcion, setSuscripcion] = useState<string | null>(null)
  const [copiado, setCopiado] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Sin claves no se puede activar nada, pero ocultar la ficha haría pensar
  // que la app no sabe avisar. Se dice qué falta.
  if (estado === 'sin-configurar')
    return (
      <Ficha icono={Iconos.senal} titulo="Avisos en este móvil" valor="sin activar">
        <p className="aclaracion">
          La app puede avisarte con una notificación cuando aparezca una oferta,
          sin usar Telegram. Falta generarlo una vez:{' '}
          <code>python -m buscador claves-push</code> y seguir los tres pasos que
          indica.
        </p>
      </Ficha>
    )

  // En un navegador sin Web Push no hay nada que ofrecer ni que explicar.
  if (estado === 'no-soportado') return null

  async function activar() {
    setError(null)
    try {
      const texto = await activarAvisos()
      if (!texto) {
        setError('No has dado permiso, así que no puedo avisarte en este móvil.')
        return
      }
      setSuscripcion(texto)
      setEstado(estadoAvisos())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se han podido activar.')
    }
  }

  async function copiar() {
    if (!suscripcion) return
    try {
      await navigator.clipboard.writeText(suscripcion)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2500)
    } catch {
      // Sin permiso de portapapeles queda el texto a la vista para copiarlo a mano.
    }
  }

  return (
    <Ficha
      icono={Iconos.senal}
      titulo="Avisos en este móvil"
      valor={estado === 'activo' ? '✓' : undefined}
    >
      {estado === 'bloqueado' ? (
        <p className="aclaracion">
          Tienes las notificaciones bloqueadas para esta web. Se cambia en los
          ajustes del navegador, en los permisos del sitio.
        </p>
      ) : (
        <>
          <p className="aclaracion">
            Notificación en el móvil cuando aparezca una oferta, sin necesidad de
            Telegram.
          </p>
          {estado !== 'activo' && (
            <button className="boton-suave" onClick={activar}>
              Avisarme en este móvil
            </button>
          )}
        </>
      )}

      {error && <p className="aclaracion aviso-error">{error}</p>}

      {suscripcion && (
        <>
          <p className="aclaracion">
            Falta un paso: copia este texto y guárdalo en GitHub como el secreto{' '}
            <strong>WEB_PUSH_SUSCRIPCION</strong>. Sin eso el aviso no sabe a qué
            móvil ir.
          </p>
          <textarea className="suscripcion" readOnly rows={3} value={suscripcion} />
          <button className="boton-suave" onClick={copiar}>
            {copiado ? '✓ Copiado' : 'Copiar el texto'}
          </button>
        </>
      )}
    </Ficha>
  )
}

/**
 * Atajo para instalar, arriba del todo.
 *
 * La tarjeta de Ajustes explica bien de qué va, pero está al final de la
 * pantalla que menos se abre: quien entra a mirar precios no llega nunca. Este
 * botón solo existe cuando el navegador ya ha ofrecido instalar —así no se
 * promete algo que luego no va a pasar— y desaparece en cuanto está instalada.
 */
function BotonInstalar() {
  const { estado, instalar } = useInstalacion()

  if (estado !== 'disponible') return null

  return (
    <button className="instalar" onClick={instalar} title="Instalar la app en este dispositivo">
      {Iconos.movil}
      Instalar
    </button>
  )
}

function PanelInstalacion() {
  const { estado, instalar, esApple } = useInstalacion()

  if (estado === 'instalada')
    return (
      <Ficha icono={Iconos.movil} titulo="App instalada" valor="✓">
        <p className="aclaracion">
          Guarda los últimos precios, así que puedes consultarlos sin cobertura.
        </p>
      </Ficha>
    )

  if (estado === 'disponible')
    return (
      <Ficha icono={Iconos.movil} titulo="Instalar la app">
        <p className="aclaracion">
          Pantalla completa, arranque más rápido y precios sin cobertura.
        </p>
        <button className="boton-suave" onClick={instalar}>
          Instalar en este dispositivo
        </button>
      </Ficha>
    )

  return (
    <Ficha icono={Iconos.movil} titulo="Instalar la app">
      <p className="aclaracion">
        {esApple ? (
          <>
            Pulsa <strong>Compartir</strong> y luego{' '}
            <strong>Añadir a pantalla de inicio</strong>.
          </>
        ) : (
          <>
            Menú <strong>⋮</strong> del navegador →{' '}
            <strong>Instalar aplicación</strong>. Si no aparece, ya la tienes.
          </>
        )}
      </p>
    </Ficha>
  )
}

/* --- Ajustes -------------------------------------------------------------- */

/**
 * Tarjeta de ajuste: icono, título, resumen a la derecha y el control debajo.
 *
 * Todos los ajustes tienen la misma forma para que la pantalla se lea de un
 * vistazo: el resumen de la derecha dice cómo está cada cosa sin abrir nada.
 */
function Ficha({
  icono,
  titulo,
  valor,
  children,
}: {
  icono: JSX.Element
  titulo: string
  valor?: ReactNode
  children?: ReactNode
}) {
  return (
    <section className="ficha">
      <header className="ficha-cabeza">
        <span className="ficha-icono">{icono}</span>
        <h3>{titulo}</h3>
        {valor && <span className="ficha-valor">{valor}</span>}
      </header>
      {children}
    </section>
  )
}

/**
 * Campañas que Renfe y Ouigo anuncian ahora mismo en su portada.
 *
 * No son precios de esta ruta y por eso viven aquí y no en las listas de
 * trenes. Las que piden una edad distinta de la configurada se descartan antes
 * de llegar aquí, así que esta lista ya viene filtrada; el aviso de Telegram
 * salta solo cuando aparece una campaña nueva.
 */
function PanelCampanas() {
  const { datos } = useDatos<Promociones>('promociones')
  const campanas = datos?.campanas ?? []

  if (!campanas.length) return null

  return (
    <Ficha
      icono={Iconos.ofertas}
      titulo="Campañas de las compañías"
      valor={`${campanas.length} activas`}
    >
      {campanas.map((c) => (
        <div key={c.huella} className="fuente">
          <span className="nombre">{c.compania}</span>
          <span className="dato">{c.texto}</span>
        </div>
      ))}
      <p className="aclaracion">
        Las que piden una edad que no es la tuya ya no aparecen. Las demás
        pueden seguir pidiendo grupo o fechas concretas: comprueba las
        condiciones antes de contar con el descuento.
      </p>
    </Ficha>
  )
}

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

  const horario = prefs.franjas.length
    ? FRANJAS.filter((f) => prefs.franjas.includes(f.id))
        .map((f) => f.nombre)
        .join(' · ')
    : 'Cualquier hora'

  const fuentesOk = datos?.fuentes.filter((f) => f.ok).length ?? 0

  return (
    <div className="ajustes">
      <div className="portada">
        <span className="emblema">{Iconos.ajustes}</span>
        <div>
          <h2>Tus ajustes</h2>
          <p>
            Elige cuándo viajas y qué quieres ver. Se guarda solo en este móvil.
          </p>
        </div>
      </div>

      <Seccion titulo="Tus viajes" />

      <button
        className="ficha interruptor"
        aria-pressed={prefs.mejorPrecio}
        onClick={() => cambiar('mejorPrecio', !prefs.mejorPrecio)}
      >
        <span className="ficha-icono">{Iconos.ofertas}</span>
        <span className="interruptor-texto">
          <strong>Mejor precio</strong>
          <span>
            Resume cada finde en un plan: la ida y la vuelta más baratas de tus
            días, con el total. Usa los días y el horario de aquí abajo.
          </span>
        </span>
        <span className="palanca">
          <span />
        </span>
      </button>

      <Ficha icono={Iconos.calendario} titulo="Días de viaje" valor="Madrid ⇄ Elche">
        {(
          [
            ['diasIda', 'Ida', recopilados.ida],
            ['diasVuelta', 'Vuelta', recopilados.vuelta],
          ] as const
        ).map(([campo, rotulo, disponibles]) => (
          <div key={campo} className="semana">
            <span className="rotulo">{rotulo}</span>
            <div className="dias">
              {DIAS_SEMANA.map((d) => {
                const hay = disponibles.has(d.dia)
                return (
                  <button
                    key={d.dia}
                    className={`dia-boton${prefs[campo].includes(d.dia) ? ' activo' : ''}${
                      hay ? '' : ' sin-datos'
                    }`}
                    aria-pressed={prefs[campo].includes(d.dia)}
                    aria-label={d.nombre}
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
        <p className="aclaracion">
          Los días apagados aún no se buscan: hay que añadirlos a{' '}
          <code>dias_ida</code> o <code>dias_vuelta</code> en{' '}
          <code>config/app.yaml</code>.
        </p>
      </Ficha>

      <Ficha icono={Iconos.reloj} titulo="Horario" valor={horario}>
        <div className="elecciones">
          {FRANJAS.map((f) => (
            <button
              key={f.id}
              className="eleccion"
              aria-pressed={prefs.franjas.includes(f.id)}
              onClick={() => alternar('franjas', f.id)}
            >
              {f.nombre}
              <span className="detalle">{horasFranja(f)}</span>
            </button>
          ))}
        </div>
      </Ficha>

      <button
        className="ficha interruptor"
        aria-pressed={prefs.soloDirectos}
        onClick={() => cambiar('soloDirectos', !prefs.soloDirectos)}
      >
        <span className="ficha-icono">{Iconos.trenes}</span>
        <span className="interruptor-texto">
          <strong>Solo Elche AV</strong>
          <span>Oculta los trenes por Alicante, con 25 min de traslado.</span>
        </span>
        <span className="palanca">
          <span />
        </span>
      </button>

      <Ficha
        icono={Iconos.billete}
        titulo="Compañías"
        valor={
          prefs.companias.length
            ? `${prefs.companias.length} de ${COMPANIAS.length}`
            : 'Todas'
        }
      >
        <div className="elecciones">
          {COMPANIAS.map((c) => (
            <button
              key={c.id}
              className="eleccion color"
              style={{ ['--tono' as string]: c.color, ['--tono-suave' as string]: c.suave }}
              aria-pressed={prefs.companias.includes(c.id)}
              title={c.descripcion}
              onClick={() => alternar('companias', c.id)}
            >
              <span className="punto" />
              {c.nombre}
            </button>
          ))}
        </div>
      </Ficha>

      <Ficha icono={Iconos.mapa} titulo="A dónde llegas">
        <div className="destinos">
          {['elche_av', 'alicante'].map((id) => {
            const d = destino(id)
            return (
              <span key={id} className="destino">
                <span className="punto" style={{ background: d.color }} />
                <strong style={{ color: d.color }}>{d.nombre}</strong>
                {d.traslado ? `+${d.traslado} min hasta Elche` : 'sin traslados'}
              </span>
            )
          })}
        </div>
      </Ficha>

      <Seccion titulo="La app" />

      <Ficha
        icono={Iconos.senal}
        titulo="Estado de las webs"
        valor={
          datos &&
          (datos.fuentes.length
            ? `${fuentesOk}/${datos.fuentes.length} ok · ${desde(datos.actualizado)}`
            : desde(datos.actualizado))
        }
      >
        {datos?.fuentes.map((f) => (
          <div key={f.fuente} className="fuente">
            <span className={`luz ${f.ok ? 'ok' : 'ko'}`} />
            <span className="nombre">{f.fuente}</span>
            <span className="dato">
              {f.ofertas} {f.ofertas === 1 ? 'precio' : 'precios'} ·{' '}
              {f.duracion_s.toFixed(0)} s
              {f.descartadas > 0 && (
                <strong style={{ color: 'var(--error)' }}>
                  {' '}
                  · {f.descartadas} descartados
                </strong>
              )}
            </span>
          </div>
        ))}
        <p className="aclaracion">
          Cada precio pasa un control de credibilidad: si una web devuelve cifras
          raras, se descartan y la fuente se pone en rojo.
        </p>
      </Ficha>

      <PanelAvisos />

      <PanelCampanas />

      <PanelInstalacion />

      <button className="restablecer" onClick={limpiar}>
        Restablecer todos los ajustes
      </button>
    </div>
  )
}
