"""Pruebas de la planificación de búsquedas y de la deduplicación entre fuentes."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from buscador.config import Busqueda, Config, Estaciones
from buscador.consultas import plan_calendario, plan_proximos_findes, rango_fechas
from buscador.modelos import Estacion, Oferta
from buscador.salida import mejores_por_tren

ATOCHA = Estacion(id="madrid_atocha", nombre="Madrid Puerta de Atocha")
ELCHE = Estacion(id="elche_av", nombre="Elche AV")
ALICANTE = Estacion(id="alicante", nombre="Alicante Terminal", traslado_min=25)


def config(
    dias_ida: list[str] | None = None,
    dias_vuelta: list[str] | None = None,
    incluir_vuelta: bool = False,
) -> Config:
    return Config(
        estaciones=Estaciones(origen=[ATOCHA], destino=[ELCHE, ALICANTE]),
        busqueda=Busqueda(
            dias_ida=dias_ida or [],
            dias_vuelta=dias_vuelta or [],
            incluir_vuelta=incluir_vuelta,
        ),
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
    assert {c.sentido for c in plan} == {"ida"}


# -- Vueltas ---------------------------------------------------------------


def test_la_vuelta_invierte_origen_y_destino():
    plan = plan_calendario(
        config(incluir_vuelta=True), date(2026, 9, 1), date(2026, 9, 1)
    )
    vueltas = [c for c in plan if c.sentido == "vuelta"]
    assert len(vueltas) == 2
    assert {c.origen.id for c in vueltas} == {"elche_av", "alicante"}
    assert {c.destino.id for c in vueltas} == {"madrid_atocha"}


def test_ida_y_vuelta_usan_dias_de_semana_distintos():
    """Sales viernes o sábado y vuelves domingo o lunes."""
    plan = plan_calendario(
        config(dias_ida=["viernes", "sabado"], dias_vuelta=["domingo", "lunes"],
               incluir_vuelta=True),
        date(2026, 9, 1),
        date(2026, 9, 30),
    )
    idas = {c.fecha.weekday() for c in plan if c.sentido == "ida"}
    vueltas = {c.fecha.weekday() for c in plan if c.sentido == "vuelta"}
    assert idas == {4, 5}      # viernes, sábado
    assert vueltas == {6, 0}   # domingo, lunes


def test_ampliar_los_dias_de_vuelta_anade_fechas():
    """Añadir martes a dias_vuelta alarga la escapada, sin tocar la ida."""
    rango = (date(2026, 9, 1), date(2026, 9, 30))
    corto = plan_calendario(
        config(dias_ida=["viernes"], dias_vuelta=["domingo"], incluir_vuelta=True), *rango
    )
    largo = plan_calendario(
        config(dias_ida=["viernes"], dias_vuelta=["domingo", "lunes", "martes"],
               incluir_vuelta=True),
        *rango,
    )
    idas_corto = [c for c in corto if c.sentido == "ida"]
    idas_largo = [c for c in largo if c.sentido == "ida"]
    assert len(idas_corto) == len(idas_largo)
    assert len([c for c in largo if c.sentido == "vuelta"]) > len(
        [c for c in corto if c.sentido == "vuelta"]
    )


# -- Próximos findes -------------------------------------------------------


def test_los_findes_cubren_una_semana_por_finde():
    """Dos findes son dos viernes de ida y dos lunes de vuelta."""
    plan = plan_proximos_findes(
        config(dias_ida=["viernes"], dias_vuelta=["lunes"], incluir_vuelta=True), 2
    )
    idas = sorted({c.fecha for c in plan if c.sentido == "ida"})
    vueltas = sorted({c.fecha for c in plan if c.sentido == "vuelta"})

    assert len(idas) == 2 and {d.weekday() for d in idas} == {4}
    assert len(vueltas) == 2 and {d.weekday() for d in vueltas} == {0}


def test_los_findes_empiezan_manana_y_no_miran_atras():
    """Hoy ya no se puede comprar para hoy: la ventana arranca mañana."""
    plan = plan_proximos_findes(config(incluir_vuelta=True), 1)
    fechas = [c.fecha for c in plan]
    hoy = date.today()

    assert min(fechas) == hoy + timedelta(days=1)
    assert max(fechas) == hoy + timedelta(days=7)


def test_mas_findes_son_mas_fechas():
    """El parámetro sirve para algo: subirlo alarga el horizonte."""
    uno = plan_proximos_findes(config(dias_ida=["viernes"]), 1)
    tres = plan_proximos_findes(config(dias_ida=["viernes"]), 3)
    assert len({c.fecha for c in tres}) == 3 * len({c.fecha for c in uno})


def test_se_puede_desactivar_la_vuelta():
    plan = plan_calendario(
        config(incluir_vuelta=False), date(2026, 9, 1), date(2026, 9, 2)
    )
    assert all(c.sentido == "ida" for c in plan)


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
