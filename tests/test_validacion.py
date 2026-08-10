"""Pruebas del control de credibilidad de los datos raspados.

Raspar una web es leer números de un HTML que puede cambiar sin avisar. Un
fallo total se detecta solo (la fuente devuelve cero), pero uno sutil —el
extractor empieza a coger la celda de al lado— pasaría desapercibido y
acabaría en el móvil como si fuera un precio real. Esto lo impide.
"""

from datetime import date, time

import pytest

from buscador.adaptadores.base import ejecutar, validar
from buscador.modelos import Consulta, Estacion, Oferta

MADRID = Estacion(id="madrid_chamartin", nombre="Madrid Chamartín")
ELCHE = Estacion(id="elche_av", nombre="Elche AV")
VIAJE = date(2026, 12, 5)

CONSULTA = Consulta(origen=MADRID, destino=ELCHE, fecha=VIAJE, adultos=1)


def oferta(**cambios) -> Oferta:
    base = dict(
        fuente="renfe",
        operador="Renfe",
        origen_id="madrid_chamartin",
        origen_nombre="Madrid Chamartín",
        destino_id="elche_av",
        destino_nombre="Elche AV",
        fecha_salida=VIAJE,
        hora_salida=time(8, 15),
        hora_llegada=time(11, 15),
        duracion_min=180,
        precio_eur=25.0,
        url_compra="https://ejemplo",
    )
    base.update(cambios)
    return Oferta(**base)


# -- Qué se acepta y qué no -------------------------------------------------


def test_una_oferta_normal_es_creible():
    assert validar(oferta(), CONSULTA) is None


@pytest.mark.parametrize("precio", [0.0, 1.5, 4.99, 700.0, 9999.0])
def test_precio_disparatado_se_rechaza(precio):
    assert "precio" in validar(oferta(precio_eur=precio), CONSULTA)


@pytest.mark.parametrize("minutos", [0, 5, 29, 700])
def test_duracion_imposible_se_rechaza(minutos):
    assert "duración" in validar(oferta(duracion_min=minutos), CONSULTA)


def test_fecha_distinta_de_la_pedida_se_rechaza():
    """El fallo real que tuvo Renfe: buscar un día y devolver el de hoy."""
    motivo = validar(oferta(fecha_salida=date(2026, 8, 10)), CONSULTA)
    assert "fecha equivocada" in motivo


def test_trayecto_distinto_se_rechaza():
    motivo = validar(oferta(destino_id="alicante"), CONSULTA)
    assert "trayecto" in motivo


# -- Efecto sobre el estado de la fuente ------------------------------------


class AdaptadorFalso:
    """Adaptador de mentira que devuelve lo que se le diga."""

    nombre = "falso"

    def __init__(self, ofertas):
        self._ofertas = ofertas

    def buscar(self, consulta):
        return self._ofertas

    def descubrir_estaciones(self, estaciones):
        return {}


def test_las_ofertas_malas_no_llegan_a_los_resultados():
    adaptador = AdaptadorFalso([oferta(), oferta(precio_eur=0.5), oferta(duracion_min=3)])
    ofertas, resultado = ejecutar(adaptador, [CONSULTA])
    assert len(ofertas) == 1
    assert resultado.descartadas == 2


def test_si_se_descarta_mas_de_lo_que_se_acepta_la_fuente_va_en_rojo():
    """Señal de que el extractor está roto, no de un dato suelto raro."""
    adaptador = AdaptadorFalso([oferta(), oferta(precio_eur=0.5), oferta(precio_eur=0.9)])
    _, resultado = ejecutar(adaptador, [CONSULTA])
    assert resultado.ok is False
    assert "no creíbles" in (resultado.error or "")


def test_un_dato_raro_suelto_no_tumba_la_fuente():
    adaptador = AdaptadorFalso(
        [oferta(), oferta(hora_salida=time(9, 0)), oferta(precio_eur=0.5)]
    )
    _, resultado = ejecutar(adaptador, [CONSULTA])
    assert resultado.ok is True
    assert resultado.ofertas == 2


def test_un_dia_sin_trenes_no_es_un_fallo():
    _, resultado = ejecutar(AdaptadorFalso([]), [CONSULTA])
    assert resultado.ok is True
    assert resultado.ofertas == 0
