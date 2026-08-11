"""Pruebas de la referencia de precio: qué suele costar cada viaje.

Es lo que permite responder "¿lo cojo ya o espero?". Lo que se protege aquí es
que la app **no opine antes de tiempo**: con dos días de datos cualquier
veredicto sería inventado, y decir "está barato" sin fundamento es peor que
no decir nada.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from buscador import historico
from buscador.config import cargar_config
from buscador.exportar import _referencias
from buscador.modelos import Oferta

VIAJE = date(2026, 12, 5)
AHORA = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)


@pytest.fixture(autouse=True)
def historico_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(historico, "DIR_HISTORICO", tmp_path / "historico")
    yield


def oferta(precio: float, hace_dias: int = 0) -> Oferta:
    return Oferta(
        fuente="ouigo",
        operador="Ouigo",
        origen_id="madrid_chamartin",
        origen_nombre="Madrid Chamartín",
        destino_id="elche_av",
        destino_nombre="Elche AV",
        fecha_salida=VIAJE,
        hora_salida=time(8, 15),
        hora_llegada=time(10, 37),
        duracion_min=142,
        precio_eur=precio,
        url_compra="https://ejemplo",
        capturado_en=AHORA - timedelta(days=hace_dias),
    )


def _con_dias(n: int) -> dict:
    """Histórico de n días, un precio por día."""
    config = cargar_config()
    ofertas = [oferta(20.0 + i, hace_dias=i) for i in range(n)]
    historico.guardar(ofertas, [])
    return _referencias(ofertas, config)


def test_con_pocos_dias_no_opina():
    salida = _con_dias(2)
    assert salida["listo"] is False
    assert salida["viajes"] == {}, "sin datos suficientes no se publica referencia"


def test_dice_cuanto_le_falta():
    """La app lo enseña para que no parezca que la función no existe."""
    salida = _con_dias(2)
    assert salida["dias_reunidos"] == 2
    assert salida["dias_necesarios"] == cargar_config().ofertas.dias_minimos_historico


def test_con_bastantes_dias_ya_publica_la_referencia():
    salida = _con_dias(12)
    assert salida["listo"] is True
    viaje = salida["viajes"]["madrid_chamartin->elche_av"][VIAJE.isoformat()]
    assert viaje["dias"] >= 10
    # Precios de 20 a 31, uno por día: la mediana cae en mitad del recorrido.
    assert 24 <= viaje["normal"] <= 27


def test_la_referencia_usa_los_minimos_del_dia():
    """Varias fuentes el mismo día no deben inflar lo que se considera normal."""
    config = cargar_config()
    ofertas = []
    for i in range(12):
        ofertas.append(oferta(20.0, hace_dias=i))
        # Otro tren del mismo día y viaje, mucho más caro.
        caro = oferta(90.0, hace_dias=i)
        caro.hora_salida = time(19, 40)
        ofertas.append(caro)
    historico.guardar(ofertas, [])

    salida = _referencias(ofertas, config)
    viaje = salida["viajes"]["madrid_chamartin->elche_av"][VIAJE.isoformat()]
    assert viaje["normal"] == 20.0, "el de 90 € no puede mover la referencia"


# -- Series para el gráfico de evolución ------------------------------------


def test_la_serie_guarda_un_punto_por_dia():
    """La vigilancia corre cada hora; el gráfico solo necesita el mínimo diario."""
    config = cargar_config()
    ofertas = []
    for dia in range(4):
        for hora in range(3):  # tres capturas del mismo día
            captura = oferta(30.0 - hora, hace_dias=dia)
            captura.capturado_en = AHORA - timedelta(days=dia, hours=hora)
            ofertas.append(captura)
    historico.guardar(ofertas, [])

    serie = _referencias(ofertas, config)["series"]["madrid_chamartin->elche_av"][
        VIAJE.isoformat()
    ]
    assert len(serie) == 4, "un punto por día, no por captura"
    assert all(precio == 28.0 for _, precio in serie), "se queda el mínimo del día"


def test_la_serie_va_ordenada_por_fecha():
    config = cargar_config()
    ofertas = [oferta(20.0 + i, hace_dias=i) for i in range(5)]
    historico.guardar(ofertas, [])

    serie = _referencias(ofertas, config)["series"]["madrid_chamartin->elche_av"][
        VIAJE.isoformat()
    ]
    dias = [dia for dia, _ in serie]
    assert dias == sorted(dias)


def test_un_solo_dia_no_es_una_evolucion():
    """Con un punto no hay curva que dibujar: no se publica."""
    config = cargar_config()
    ofertas = [oferta(25.0)]
    historico.guardar(ofertas, [])
    assert _referencias(ofertas, config)["series"] == {}
