"""Pruebas de la lógica que decide qué es una ganga.

Es la parte que no depende de ninguna web externa y la que más daño hace si
falla en silencio: o te pierdes una oferta o te llena el móvil de avisos.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from buscador.config import Config, Estaciones, Ofertas
from buscador.historico import Referencia, minimos_diarios
from buscador.modelos import Estacion, Oferta
from buscador.ofertas import detectar

HOY = datetime.now(timezone.utc).date()
VIAJE = date(2026, 12, 5)


def oferta(precio: float, capturado_hace: int = 0, hora: int = 8, **extra) -> Oferta:
    return Oferta(
        fuente=extra.get("fuente", "ouigo"),
        operador=extra.get("operador", "Ouigo"),
        origen_id="madrid_chamartin",
        origen_nombre="Madrid Chamartín",
        destino_id="elche_av",
        destino_nombre="Elche AV",
        fecha_salida=extra.get("fecha_salida", VIAJE),
        hora_salida=time(hora, 15),
        hora_llegada=time(hora + 2, 37),
        duracion_min=142,
        precio_eur=precio,
        url_compra="https://ejemplo",
        capturado_en=datetime.now(timezone.utc) - timedelta(days=capturado_hace),
    )


@pytest.fixture
def config() -> Config:
    return Config(
        estaciones=Estaciones(
            origen=[Estacion(id="madrid_chamartin", nombre="Madrid Chamartín")],
            destino=[Estacion(id="elche_av", nombre="Elche AV")],
        ),
        ofertas=Ofertas(
            caida_minima_pct=25,
            dias_historico=30,
            dias_minimo_reciente=14,
            dias_minimos_historico=10,
            umbral_absoluto_eur=25.0,
        ),
    )


def historico_estable(precio: float = 40.0, dias: int = 12) -> list[Oferta]:
    """Un precio constante durante varios días, para tener mediana fiable."""
    return [oferta(precio, capturado_hace=d) for d in range(1, dias + 1)]


# -- Agregación del histórico ----------------------------------------------


def test_minimo_diario_toma_el_mas_barato_del_dia():
    ofertas = [oferta(50, capturado_hace=1), oferta(30, capturado_hace=1, hora=10)]
    agrupado = minimos_diarios(ofertas)
    (por_dia,) = agrupado.values()
    assert list(por_dia.values()) == [30.0]


def test_mediana_ignora_lo_anterior_a_la_ventana():
    ofertas = [oferta(10, capturado_hace=90)] + historico_estable(40, dias=11)
    referencia = Referencia(ofertas)
    mediana, dias = referencia.mediana("madrid_chamartin->elche_av", VIAJE, dias=30)
    assert mediana == 40.0
    assert dias == 11  # el de hace 90 días queda fuera


# -- Detección de gangas ----------------------------------------------------


def test_avisa_cuando_cae_por_debajo_del_umbral(config):
    referencia = Referencia(historico_estable(40.0))
    gangas = detectar([oferta(28.0)], referencia, config)
    assert len(gangas) == 1
    assert gangas[0].caida_pct == pytest.approx(30.0)
    assert gangas[0].mediana_eur == 40.0


def test_no_avisa_si_la_bajada_es_pequena(config):
    referencia = Referencia(historico_estable(40.0))
    # 32 € es un 20% de bajada: por debajo del 25% exigido.
    assert detectar([oferta(32.0)], referencia, config) == []


def test_no_repite_un_precio_ya_visto_igual_de_bajo(config):
    # Ya se vio a 28 € hace dos días: hoy a 28 € no es noticia.
    referencia = Referencia(historico_estable(40.0) + [oferta(28.0, capturado_hace=2)])
    assert detectar([oferta(28.0)], referencia, config) == []


def test_avisa_si_mejora_el_minimo_reciente(config):
    referencia = Referencia(historico_estable(40.0) + [oferta(28.0, capturado_hace=2)])
    gangas = detectar([oferta(25.0)], referencia, config)
    assert len(gangas) == 1


def test_sin_historico_usa_el_umbral_absoluto(config):
    referencia = Referencia([])
    assert detectar([oferta(19.0)], referencia, config)      # por debajo de 25 €
    assert detectar([oferta(40.0)], referencia, config) == []


def test_historico_insuficiente_no_usa_la_mediana(config):
    """Con 3 días de datos no se puede afirmar que 30 € sea una ganga."""
    referencia = Referencia(historico_estable(80.0, dias=3))
    assert detectar([oferta(30.0)], referencia, config) == []


def test_un_solo_aviso_por_viaje(config):
    """De varios trenes del mismo día solo se avisa del más barato."""
    referencia = Referencia(historico_estable(40.0))
    gangas = detectar([oferta(29.0, hora=8), oferta(26.0, hora=16)], referencia, config)
    assert len(gangas) == 1
    assert gangas[0].oferta.precio_eur == 26.0


def test_viajes_distintos_generan_avisos_distintos(config):
    otro = date(2026, 12, 6)
    referencia = Referencia(
        historico_estable(40.0)
        + [oferta(40.0, capturado_hace=d, fecha_salida=otro) for d in range(1, 13)]
    )
    gangas = detectar([oferta(28.0), oferta(27.0, fecha_salida=otro)], referencia, config)
    assert len(gangas) == 2
