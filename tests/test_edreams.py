"""Pruebas del adaptador de eDreams.

Lo que se vigila aquí es sobre todo **de qué precio nos fiamos**. eDreams
enseña dos por cada tren: el normal y una "tarifa Prime" mucho más barata que
exige suscribirse. El segundo es el que sale más grande y en color, así que es
justo el que un extractor descuidado cogería; guardarlo llenaría el histórico
de precios que nadie puede pagar y dispararía alertas de gangas falsas.
"""

from datetime import date

from buscador.adaptadores.edreams import AdaptadorEdreams, _a_precio
from buscador.config import cargar_config
from buscador.modelos import Consulta, Estacion

MADRID = Estacion(id="madrid_chamartin", nombre="Madrid Chamartín")
ALICANTE = Estacion(id="alicante", nombre="Alicante Terminal")
CONSULTA = Consulta(origen=MADRID, destino=ALICANTE, fecha=date(2026, 8, 29), adultos=1)

#: Una tarjeta tal y como la devuelve JS_EXTRAER, con los dos precios.
CRUDO_CON_PRIME = {
    "operador": "AVLO",
    "salida": "06:15",
    "llegada": "08:48",
    "duracion_min": 153,
    "origen": "Madrid, Chamartin",
    "destino": "Alicante, Alicante T...",
    "precio": "35",  # el sin descuento; el Prime era 16 €
    "directo": True,
}


def _adaptador() -> AdaptadorEdreams:
    return AdaptadorEdreams(cargar_config())


def test_toma_el_precio_sin_descuento():
    ofertas = _adaptador()._a_ofertas([CRUDO_CON_PRIME], CONSULTA, "https://x")
    assert len(ofertas) == 1
    assert ofertas[0].precio_eur == 35.0, "nunca el precio Prime"


def test_traduce_los_nombres_de_operador():
    """'OUIGO ES' es como lo llama eDreams; la app colorea por 'Ouigo'."""
    crudo = {**CRUDO_CON_PRIME, "operador": "OUIGO ES"}
    assert _adaptador()._a_ofertas([crudo], CONSULTA, "x")[0].operador == "Ouigo"


def test_descarta_trenes_a_otra_estacion():
    """Alicante entra en eDreams como ciudad: hay que comprobar la estación."""
    crudo = {**CRUDO_CON_PRIME, "destino": "Alicante, Sant Vicent"}
    assert _adaptador()._a_ofertas([crudo], CONSULTA, "x") == []


def test_descarta_tarjetas_sin_precio_o_sin_horas():
    incompletos = [
        {**CRUDO_CON_PRIME, "precio": None},
        {**CRUDO_CON_PRIME, "salida": None},
        {**CRUDO_CON_PRIME, "llegada": "no es una hora"},
    ]
    assert _adaptador()._a_ofertas(incompletos, CONSULTA, "x") == []


def test_no_repite_el_mismo_tren():
    """eDreams repite arriba la tarjeta destacada ('Más barato', 'Mejor')."""
    assert len(_adaptador()._a_ofertas([CRUDO_CON_PRIME] * 3, CONSULTA, "x")) == 1


def test_el_enlace_lleva_a_la_busqueda_concreta():
    """La única fuente que permite enlazar a la ruta y el día pedidos."""
    enlace = _adaptador().enlace(CONSULTA)
    assert "from=1070286" in enlace and "to=9629" in enlace
    assert "dep=2026-08-29" in enlace


def test_lee_precios_en_formato_espanol():
    assert _a_precio("1.234,56 €") == 1234.56
    assert _a_precio("45 €") == 45.0
    assert _a_precio("sin precio") is None
