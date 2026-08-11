"""Pruebas de cómo se avisa, que es distinto de qué se avisa.

El primer día el buscador encontró 32 ofertas por debajo del umbral y el envío
era un mensaje por oferta: 32 notificaciones seguidas. Un aviso que no se lee
no sirve de nada, así que en cuanto son varias van juntas en un solo mensaje.
"""

from datetime import date, time

from buscador.avisos.telegram import AVISOS_SUELTOS, EN_EL_RESUMEN, _resumen
from buscador.fechas import dia_corto, dia_largo
from buscador.modelos import Oferta
from buscador.ofertas import Ganga


def ganga(precio: float, dia: int = 1) -> Ganga:
    return Ganga(
        oferta=Oferta(
            fuente="ouigo",
            operador="Ouigo",
            origen_id="madrid_chamartin",
            origen_nombre="Madrid Chamartín",
            destino_id="elche_av",
            destino_nombre="Elche AV",
            fecha_salida=date(2026, 10, dia),
            hora_salida=time(6, 15),
            hora_llegada=time(8, 48),
            duracion_min=153,
            precio_eur=precio,
            url_compra="https://ejemplo",
        ),
        motivo="Por debajo de 15 €.",
    )


def test_el_resumen_ordena_de_mas_barata_a_menos():
    texto = _resumen([ganga(30.0), ganga(9.0), ganga(19.0)])
    assert texto.index("9.00") < texto.index("19.00") < texto.index("30.00")


def test_el_resumen_no_lista_las_treinta_y_dos():
    """Se detallan unas pocas y el resto se cuenta: el mensaje debe caber."""
    texto = _resumen([ganga(10.0 + i, dia=1 + i % 28) for i in range(32)])
    assert texto.count("€</b>") == EN_EL_RESUMEN
    assert f"{32 - EN_EL_RESUMEN} más" in texto


def test_el_resumen_dice_cuantas_hay_en_total():
    assert "32 ofertas destacadas" in _resumen([ganga(10.0 + i) for i in range(32)])


def test_con_pocas_no_hay_coletilla_de_sobrantes():
    assert "más en la app" not in _resumen([ganga(9.0), ganga(12.0)])


def test_se_agrupa_a_partir_de_dos():
    """Con una o dos, el mensaje detallado es más cómodo que un resumen."""
    assert AVISOS_SUELTOS == 2


def test_las_fechas_van_en_espanol():
    """En GitHub la máquina está en inglés y salía 'Thu 01/10'."""
    jueves = date(2026, 10, 1)
    assert dia_corto(jueves) == "jue 01/10"
    assert dia_largo(jueves) == "jueves 1 de octubre de 2026"


def test_el_aviso_suelto_lleva_fecha_en_espanol():
    assert "jueves 1 de octubre" in ganga(9.0).texto()
