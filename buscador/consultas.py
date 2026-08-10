"""Construcción del plan de consultas a partir de la configuración."""

from __future__ import annotations

from datetime import date, timedelta

from .config import Config
from .modelos import Consulta, Estacion


def rango_fechas(
    desde: date, hasta: date, config: Config, sentido: str = "ida"
) -> list[date]:
    """Días entre dos fechas, filtrados por los días configurados de ese sentido."""
    if hasta < desde:
        raise ValueError(f"La fecha final ({hasta}) es anterior a la inicial ({desde}).")

    permitidos = config.busqueda.indices_dias_semana(sentido)
    dias = []
    actual = desde
    while actual <= hasta:
        if permitidos is None or actual.weekday() in permitidos:
            dias.append(actual)
        actual += timedelta(days=1)
    return dias


def plan_calendario(
    config: Config,
    desde: date,
    hasta: date,
    origenes: list[Estacion] | None = None,
    destinos: list[Estacion] | None = None,
) -> list[Consulta]:
    """Ida y, si está activada, vuelta, en todos los días que correspondan.

    Ida y vuelta se planifican por separado porque tienen días distintos: se
    sale viernes o sábado y se vuelve domingo o lunes. Con una sola lista de
    días no habría manera de expresarlo.
    """
    origenes = origenes or config.estaciones.origen
    destinos = destinos or config.estaciones.destino

    consultas = [
        Consulta(
            origen=origen,
            destino=destino,
            fecha=dia,
            adultos=config.pasajeros.adultos,
            sentido="ida",
        )
        for dia in rango_fechas(desde, hasta, config, "ida")
        for origen in origenes
        for destino in destinos
    ]

    if config.busqueda.incluir_vuelta:
        consultas += [
            Consulta(
                origen=destino,      # la vuelta sale del destino…
                destino=origen,      # …y llega al origen
                fecha=dia,
                adultos=config.pasajeros.adultos,
                sentido="vuelta",
            )
            for dia in rango_fechas(desde, hasta, config, "vuelta")
            for origen in origenes
            for destino in destinos
        ]

    return consultas


def plan_top_dias(config: Config, cuantos: int) -> list[Consulta]:
    """Consultas solo para los días más baratos que ya conocemos.

    Barrer 90 días con todas las fuentes es inviable: Renfe tarda medio minuto
    por consulta. El reparto que hace funcionar esto es: una fuente rápida
    (Ouigo) dibuja el mapa de precios de todo el horizonte, y después las
    fuentes lentas solo miran los días que han salido baratos, que son los
    únicos en los que merece la pena comparar operadores.
    """
    import json

    from .config import DIR_DATOS

    ruta_calendario = DIR_DATOS / "calendario.json"
    if not ruta_calendario.exists():
        raise FileNotFoundError(
            "No hay data/calendario.json todavía. Ejecuta antes un barrido "
            "completo con una fuente rápida:\n"
            "  python -m buscador buscar --fuentes ouigo --guardar"
        )

    with ruta_calendario.open(encoding="utf-8") as fichero:
        calendario = json.load(fichero)

    hoy = date.today()
    ids_destino = {e.id for e in config.estaciones.destino}
    consultas: list[Consulta] = []
    for clave, por_dia in (calendario.get("rutas") or {}).items():
        origen_id, _, destino_id = clave.partition("->")
        try:
            origen = config.estaciones.por_id(origen_id)
            destino = config.estaciones.por_id(destino_id)
        except KeyError:
            continue  # ruta de una configuración anterior

        futuros = [
            (precio, date.fromisoformat(dia))
            for dia, precio in por_dia.items()
            if date.fromisoformat(dia) > hoy
        ]
        # La vuelta sale de una estación de destino: lo deducimos de la ruta.
        sentido = "vuelta" if origen_id in ids_destino else "ida"

        for _, dia in sorted(futuros)[:cuantos]:
            consultas.append(
                Consulta(
                    origen=origen,
                    destino=destino,
                    fecha=dia,
                    adultos=config.pasajeros.adultos,
                    sentido=sentido,
                )
            )
    return consultas


def plan_vigilancias(config: Config) -> list[Consulta]:
    """Consultas derivadas de config/vigilancias.yaml (ida y, si hay, vuelta)."""
    from .config import cargar_vigilancias

    consultas: list[Consulta] = []
    for vigilancia in cargar_vigilancias():
        origen = config.estaciones.por_id(vigilancia.origen)
        destino = config.estaciones.por_id(vigilancia.destino)
        consultas.append(
            Consulta(
                origen=origen,
                destino=destino,
                fecha=vigilancia.ida,
                adultos=config.pasajeros.adultos,
                sentido="ida",
            )
        )
        if vigilancia.vuelta:
            consultas.append(
                Consulta(
                    origen=destino,
                    destino=origen,
                    fecha=vigilancia.vuelta,
                    adultos=config.pasajeros.adultos,
                    sentido="vuelta",
                )
            )
    return consultas
