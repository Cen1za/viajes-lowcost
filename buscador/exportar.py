"""Genera los ficheros JSON que consume la PWA.

La aplicación del móvil no llama a ninguna API: lee estos ficheros, que
GitHub Actions regenera y comitea en cada ejecución.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from . import historico
from .config import DIR_DATOS, Config
from .historico import escribir_json
from .modelos import Oferta, ResultadoFuente
from .ofertas import Ganga

#: Días de histórico que se consideran "precio actual". Una ejecución con
#: --top-dias solo mira un puñado de fechas; si generásemos el calendario con
#: lo que acaba de encontrar, borraríamos el resto del horizonte.
DIAS_VIGENCIA = 3


def _ahora() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _oferta_json(oferta: Oferta) -> dict:
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
        "url": oferta.url_compra,
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


def _calendario(ofertas: list[Oferta]) -> dict:
    """Precio mínimo por ruta y día, para el mapa de calor de la PWA."""
    minimos: dict[str, dict[str, float]] = defaultdict(dict)
    nombres: dict[str, str] = {}
    sentidos: dict[str, str] = {}
    operadores: dict[str, dict[str, str]] = defaultdict(dict)

    for oferta in ofertas:
        dia = oferta.fecha_salida.isoformat()
        actual = minimos[oferta.ruta].get(dia)
        if actual is None or oferta.precio_eur < actual:
            minimos[oferta.ruta][dia] = round(oferta.precio_eur, 2)
            # Quién pone el precio más bajo ese día: la app colorea con esto.
            operadores[oferta.ruta][dia] = oferta.operador
        nombres[oferta.ruta] = f"{oferta.origen_nombre} → {oferta.destino_nombre}"
        sentidos[oferta.ruta] = oferta.sentido

    return {
        "actualizado": _ahora(),
        "nombres": nombres,
        "sentidos": sentidos,
        "operadores": {r: dict(sorted(d.items())) for r, d in operadores.items()},
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
