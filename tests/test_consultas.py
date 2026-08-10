"""Pruebas de la planificación de búsquedas y de la deduplicación entre fuentes."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from buscador.config import Busqueda, Config, Estaciones
from buscador.consultas import plan_calendario, rango_fechas
from buscador.modelos import Estacion, Oferta
from buscador.salida import mejores_por_tren

ATOCHA = Estacion(id="madrid_atocha", nombre="Madrid Puerta de Atocha")
ELCHE = Estacion(id="elche_av", nombre="Elche AV")
ALICANTE = Estacion(id="alicante", nombre="Alicante Terminal", traslado_min=25)


def config(dias_semana: list[str] | None = None) -> Config:
    return Config(
        estaciones=Estaciones(origen=[ATOCHA], destino=[ELCHE, ALICANTE]),
        busqueda=Busqueda(dias_semana=dias_semana or []),
    )


def test_rango_incluye_los_dos_extremos():
    dias = rango_fechas(date(2026, 9, 1), date(2026, 9, 3), config())
    assert dias == [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]


def test_filtra_por_dia_de_la_semana():
    # Del 1 al 30 de septiembre de 2026, solo viernes y domingos.
    dias = rango_fechas(date(2026, 9, 1), date(2026, 9, 30), config(["viernes", "domingo"]))
    assert {d.weekday() for d in dias} == {4, 6}


def test_dia_de_la_semana_admite_acentos():
    dias = rango_fechas(date(2026, 9, 1), date(2026, 9, 30), config(["miércoles"]))
    assert {d.weekday() for d in dias} == {2}


def test_dia_de_la_semana_invalido_avisa_claro():
    with pytest.raises(ValueError, match="lunes"):
        rango_fechas(date(2026, 9, 1), date(2026, 9, 2), config(["jueces"]))


def test_rango_invertido_es_un_error():
    with pytest.raises(ValueError, match="anterior"):
        rango_fechas(date(2026, 9, 10), date(2026, 9, 1), config())


def test_plan_combina_origenes_destinos_y_dias():
    plan = plan_calendario(config(), date(2026, 9, 1), date(2026, 9, 2))
    assert len(plan) == 2 * 1 * 2  # 2 días × 1 origen × 2 destinos
    assert {c.destino.id for c in plan} == {"elche_av", "alicante"}


# -- Deduplicación entre fuentes -------------------------------------------


def tren(fuente: str, precio: float, hora: int = 8, operador: str = "Ouigo") -> Oferta:
    return Oferta(
        fuente=fuente,
        operador=operador,
        origen_id="madrid_chamartin",
        origen_nombre="Madrid Chamartín",
        destino_id="elche_av",
        destino_nombre="Elche AV",
        fecha_salida=date(2026, 9, 12),
        hora_salida=time(hora, 15),
        hora_llegada=time(hora + 3, 0),
        duracion_min=165,
        precio_eur=precio,
        url_compra="https://ejemplo",
        capturado_en=datetime.now(timezone.utc),
    )


def test_el_mismo_tren_en_dos_fuentes_se_colapsa_al_mas_barato():
    mejores = mejores_por_tren([tren("trainline", 33.0), tren("ouigo", 25.0)])
    assert len(mejores) == 1
    assert mejores[0].precio_eur == 25.0
    assert mejores[0].fuente == "ouigo"


def test_trenes_distintos_no_se_mezclan():
    mejores = mejores_por_tren([tren("ouigo", 25.0, hora=8), tren("ouigo", 25.0, hora=16)])
    assert len(mejores) == 2


def test_operadores_distintos_a_la_misma_hora_son_trenes_distintos():
    mejores = mejores_por_tren(
        [tren("ouigo", 25.0, operador="Ouigo"), tren("renfe", 30.0, operador="AVE")]
    )
    assert len(mejores) == 2
