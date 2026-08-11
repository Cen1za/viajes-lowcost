"""Genera los ficheros JSON que consume la PWA.

La aplicación del móvil no llama a ninguna API: lee estos ficheros, que
GitHub Actions regenera y comitea en cada ejecución.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from . import historico
from .config import DIR_DATOS, Config
from .enlaces import web_operador
from .historico import Referencia, escribir_json
from .modelos import Oferta, ResultadoFuente
from .ofertas import Ganga

#: Días de histórico que se consideran "precio actual". Una ejecución con
#: --top-dias solo mira un puñado de fechas; si generásemos el calendario con
#: lo que acaba de encontrar, borraríamos el resto del horizonte.
DIAS_VIGENCIA = 3


def _ahora() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


#: Fuentes cuyo enlace de búsqueda se puede pegar en otro navegador y sigue
#: funcionando. eDreams mete trayecto y fecha en la URL; Renfe la firma con un
#: token de sesión y Ouigo ignora los parámetros, así que de esas solo se puede
#: ofrecer la portada. Ver buscador/enlaces.py.
FUENTES_CON_BUSQUEDA = {"edreams"}


def _oferta_json(oferta: Oferta) -> dict:
    # El enlace se recalcula aquí en vez de usar el guardado: así los registros
    # antiguos —que llevaban la URL de sesión de Renfe, inservible fuera de su
    # navegador— quedan arreglados sin migrar el fichero.
    enlace_operador = web_operador(oferta.operador)
    # …pero cuando la fuente sí da una búsqueda enlazable, se publica aparte:
    # llegar a los resultados de tu fecha ahorra teclear el viaje entero.
    busqueda = oferta.url_compra if oferta.fuente in FUENTES_CON_BUSQUEDA else None
    return {
        "fuente": oferta.fuente,
        "operador": oferta.operador,
        "sentido": oferta.sentido,
        "origen": oferta.origen_nombre,
        "destino": oferta.destino_nombre,
        "origen_id": oferta.origen_id,
        "destino_id": oferta.destino_id,
        "fecha": oferta.fecha_salida.isoformat(),
        "salida": f"{oferta.hora_salida:%H:%M}",
        "llegada": f"{oferta.hora_llegada:%H:%M}",
        "duracion_min": oferta.duracion_min,
        "precio": round(oferta.precio_eur, 2),
        "tarifa": oferta.tarifa,
        "plazas": oferta.plazas_restantes,
        "url": enlace_operador,
        "url_busqueda": busqueda,
    }


def exportar_todo(
    ofertas: list[Oferta],
    resultados: list[ResultadoFuente],
    gangas: list[Ganga],
    config: Config,
) -> None:
    """Regenera los JSON de la PWA.

    El estado de las fuentes y las gangas salen de esta ejecución, pero el
    listado de precios y el calendario se reconstruyen desde el histórico
    reciente: así una ejecución parcial completa la foto en lugar de recortarla.
    """
    vigentes = _vigentes(ofertas)
    escribir_json(DIR_DATOS / "latest.json", _latest(vigentes, config))
    escribir_json(DIR_DATOS / "calendario.json", _calendario(vigentes))
    escribir_json(DIR_DATOS / "estado_fuentes.json", _estado(resultados))
    escribir_json(DIR_DATOS / "gangas.json", _gangas(gangas, config))
    escribir_json(DIR_DATOS / "referencias.json", _referencias(vigentes, config))


def _vigentes(recientes: list[Oferta]) -> list[Oferta]:
    """Última captura conocida de cada tren, dentro de la ventana de vigencia.

    Descarta además los viajes cuya fecha ya ha pasado.
    """
    corte_captura = datetime.now(timezone.utc).date() - timedelta(days=DIAS_VIGENCIA)
    hoy = date.today()

    candidatas = historico.cargar(desde=corte_captura) + recientes
    ultimas: dict[str, Oferta] = {}
    for oferta in candidatas:
        if oferta.fecha_salida < hoy:
            continue
        actual = ultimas.get(oferta.clave_tren)
        if actual is None or oferta.capturado_en >= actual.capturado_en:
            ultimas[oferta.clave_tren] = oferta
    return list(ultimas.values())


def _latest(ofertas: list[Oferta], config: Config) -> dict:
    """Los trenes más baratos, ya deduplicados entre fuentes."""
    mejores: dict[str, Oferta] = {}
    for oferta in ofertas:
        actual = mejores.get(oferta.clave_tren)
        if actual is None or oferta.precio_eur < actual.precio_eur:
            mejores[oferta.clave_tren] = oferta

    traslados = {
        estacion.id: estacion.traslado_min for estacion in config.estaciones.todas()
    }
    ordenadas = sorted(mejores.values(), key=lambda o: (o.fecha_salida, o.precio_eur))

    return {
        "actualizado": _ahora(),
        "traslado_min": traslados,
        "trenes": [_oferta_json(o) for o in ordenadas],
    }


def _referencias(ofertas: list[Oferta], config: Config) -> dict:
    """Qué suele costar cada viaje, para poder decir si hoy está barato.

    Es la pregunta de verdad al comprar un billete -¿lo cojo ya o espero?- y
    no se puede responder con el precio de hoy a secas: hacen falta días.
    Mientras no los haya se devuelve `listo: false` y la app calla en vez de
    inventarse un veredicto con dos datos.

    La referencia es la mediana de los mínimos diarios de ese viaje, la misma
    que decide las gangas, así que la app y los avisos cuentan lo mismo.
    """
    referencia = Referencia(historico.cargar())
    ajustes = config.ofertas
    hoy = date.today()

    viajes: dict[str, dict[str, dict]] = defaultdict(dict)
    dias_maximos = 0

    for oferta in ofertas:
        dia = oferta.fecha_salida.isoformat()
        if dia in viajes[oferta.ruta]:
            continue
        mediana, dias = referencia.mediana(
            oferta.ruta, oferta.fecha_salida, ajustes.dias_historico
        )
        dias_maximos = max(dias_maximos, dias)
        if mediana is None or dias < ajustes.dias_minimos_historico:
            continue
        viajes[oferta.ruta][dia] = {"normal": round(mediana, 2), "dias": dias}

    return {
        "actualizado": _ahora(),
        # Con esto la app sabe si puede opinar, y cuánto le falta si no.
        "listo": dias_maximos >= ajustes.dias_minimos_historico,
        "dias_reunidos": dias_maximos,
        "dias_necesarios": ajustes.dias_minimos_historico,
        "desde": hoy.isoformat(),
        "viajes": {r: dict(sorted(d.items())) for r, d in viajes.items() if d},
        "series": _series(ofertas, ajustes.dias_historico),
    }


def _series(ofertas: list[Oferta], dias: int) -> dict:
    """Cómo ha ido cambiando el precio de cada viaje, día a día.

    Se guarda solo el mínimo de cada jornada, no cada captura: la vigilancia
    corre cada hora y el detalle no aporta nada a la vista de "cómo va este
    viaje", pero multiplicaría por veinte lo que se descarga el móvil.

    Formato apretado a propósito -listas de [día, precio] con el día en
    AAAA-MM-DD- porque esto lo lee un teléfono, a veces con mala cobertura.
    """
    corte = date.today() - timedelta(days=dias)
    minimos: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))

    interesan = {(o.ruta, o.fecha_salida.isoformat()) for o in ofertas}

    for oferta in historico.cargar(desde=corte):
        viaje = oferta.fecha_salida.isoformat()
        if (oferta.ruta, viaje) not in interesan:
            continue  # viajes que ya no se enseñan: no hay que arrastrarlos
        dia = oferta.capturado_en.date().isoformat()
        previo = minimos[oferta.ruta][viaje].get(dia)
        if previo is None or oferta.precio_eur < previo:
            minimos[oferta.ruta][viaje][dia] = round(oferta.precio_eur, 2)

    series = {
        ruta: {
            viaje: [[dia, precio] for dia, precio in sorted(dias_precio.items())]
            # Un solo punto no es una evolución: no se publica.
            for viaje, dias_precio in viajes.items()
            if len(dias_precio) > 1
        }
        for ruta, viajes in minimos.items()
    }
    # Y una ruta sin ningún viaje que enseñar tampoco: sería una clave vacía
    # viajando hasta el móvil para nada.
    return {ruta: viajes for ruta, viajes in series.items() if viajes}


def _calendario(ofertas: list[Oferta]) -> dict:
    """Precio mínimo por ruta y día, para el mapa de calor de la PWA."""
    minimos: dict[str, dict[str, float]] = defaultdict(dict)
    nombres: dict[str, str] = {}
    sentidos: dict[str, str] = {}
    operadores: dict[str, dict[str, str]] = defaultdict(dict)
    horarios: dict[str, dict[str, str]] = defaultdict(dict)

    for oferta in ofertas:
        dia = oferta.fecha_salida.isoformat()
        actual = minimos[oferta.ruta].get(dia)
        if actual is None or oferta.precio_eur < actual:
            minimos[oferta.ruta][dia] = round(oferta.precio_eur, 2)
            # Quién y a qué hora pone el precio más bajo de ese día: un
            # calendario sin hora no dice si el barato sale a las 6 o a las 21.
            operadores[oferta.ruta][dia] = oferta.operador
            horarios[oferta.ruta][dia] = (
                f"{oferta.hora_salida:%H:%M}–{oferta.hora_llegada:%H:%M}"
            )
        nombres[oferta.ruta] = f"{oferta.origen_nombre} → {oferta.destino_nombre}"
        sentidos[oferta.ruta] = oferta.sentido

    return {
        "actualizado": _ahora(),
        "nombres": nombres,
        "sentidos": sentidos,
        "operadores": {r: dict(sorted(d.items())) for r, d in operadores.items()},
        "horarios": {r: dict(sorted(d.items())) for r, d in horarios.items()},
        "rutas": {r: dict(sorted(d.items())) for r, d in minimos.items()},
    }


def _estado(resultados: list[ResultadoFuente]) -> dict:
    return {
        "actualizado": _ahora(),
        "fuentes": [
            {
                "fuente": r.fuente,
                "ok": r.ok,
                "ofertas": r.ofertas,
                "descartadas": r.descartadas,
                "duracion_s": r.duracion_s,
                "error": r.error,
            }
            for r in resultados
        ],
    }


def _gangas(gangas: list[Ganga], config: Config) -> dict:
    return {
        "actualizado": _ahora(),
        # Mismo mapa que en latest.json: la app necesita saber si el viaje
        # obliga a un traslado desde Alicante también aquí.
        "traslado_min": {e.id: e.traslado_min for e in config.estaciones.todas()},
        "ofertas": [
            {
                **_oferta_json(g.oferta),
                "motivo": g.motivo,
                "mediana": g.mediana_eur,
                "caida_pct": g.caida_pct,
            }
            for g in gangas
        ],
    }
