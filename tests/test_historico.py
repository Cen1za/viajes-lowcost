"""Pruebas del guardado del histórico.

Lo importante aquí es que no engorde sin aportar nada: la vigilancia corre
cada hora y la mayoría de las veces los precios no se han movido.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from buscador import historico
from buscador.modelos import Oferta

VIAJE = date(2026, 12, 5)

#: Momento de referencia de las capturas, anclado al mediodía de hoy.
#: Con `datetime.now()` a secas estas pruebas fallaban si se ejecutaban entre
#: las 00:00 y las 02:00 UTC: una captura "de hace dos horas" caía en la
#: jornada anterior y entonces guardar un punto nuevo es justo lo que toca
#: hacer, porque la mediana necesita un dato por día. El fallo era del reloj,
#: no del código, y con el mediodía como origen hay margen de sobra por los
#: dos lados.
AHORA = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)


@pytest.fixture(autouse=True)
def historico_temporal(tmp_path, monkeypatch):
    """Aísla cada prueba en su propia carpeta de histórico."""
    monkeypatch.setattr(historico, "DIR_HISTORICO", tmp_path / "historico")
    yield


def oferta(precio: float, hace_horas: float = 0, hora: int = 8) -> Oferta:
    return Oferta(
        fuente="ouigo",
        operador="Ouigo",
        origen_id="madrid_chamartin",
        origen_nombre="Madrid Chamartín",
        destino_id="elche_av",
        destino_nombre="Elche AV",
        fecha_salida=VIAJE,
        hora_salida=time(hora, 15),
        hora_llegada=time(hora + 2, 37),
        duracion_min=142,
        precio_eur=precio,
        url_compra="https://ejemplo",
        capturado_en=AHORA - timedelta(hours=hace_horas),
    )


def test_guarda_lo_que_no_conocia():
    assert historico.guardar([oferta(25.0)], []) == 1
    assert len(historico.cargar()) == 1


def test_no_repite_el_mismo_precio_el_mismo_dia():
    previas = [oferta(25.0, hace_horas=2)]
    historico.guardar(previas, [])
    assert historico.guardar([oferta(25.0)], previas) == 0


def test_si_el_precio_cambia_si_lo_guarda():
    previas = [oferta(25.0, hace_horas=2)]
    historico.guardar(previas, [])
    assert historico.guardar([oferta(19.0)], previas) == 1


def test_trenes_distintos_se_guardan_por_separado():
    assert historico.guardar([oferta(25.0, hora=8), oferta(25.0, hora=16)], []) == 2


def test_una_bajada_minima_no_cuenta_como_cambio():
    """Diferencias por debajo del céntimo son ruido de redondeo."""
    previas = [oferta(25.0, hace_horas=1)]
    assert historico.guardar([oferta(25.001)], previas) == 0


def test_muchas_capturas_iguales_el_mismo_dia_dejan_un_registro():
    """El caso real: la vigilancia horaria de un día sin cambios de precio."""
    acumulado: list[Oferta] = []
    for minuto in range(24):
        historico.guardar([oferta(25.0, hace_horas=minuto / 60)], acumulado)
        acumulado = historico.cargar()
    assert len(acumulado) == 1


def test_cada_dia_deja_su_propio_punto():
    """La mediana necesita un dato por día aunque el precio no se mueva."""
    ayer = [oferta(25.0, hace_horas=26)]
    historico.guardar(ayer, [])
    historico.guardar([oferta(25.0)], ayer)
    assert len(historico.cargar()) == 2
