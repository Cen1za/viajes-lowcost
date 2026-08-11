"""Pruebas de los avisos por notificación del móvil.

Lo importante: sin configurar no puede dar problemas. Los secretos son
opcionales, y quien no los ponga tiene que poder seguir usando el buscador y
Telegram como si esto no existiera.
"""

import json
from datetime import date, time

import pytest

from buscador.avisos import avisar_de_gangas, webpush
from buscador.modelos import Oferta
from buscador.ofertas import Ganga

SUSCRIPCION = json.dumps(
    {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}
)


@pytest.fixture(autouse=True)
def sin_secretos(monkeypatch):
    """Cada prueba parte de un entorno limpio, sin secretos heredados."""
    for clave in ("VAPID_CLAVE_PRIVADA", "VAPID_ASUNTO", "WEB_PUSH_SUSCRIPCION"):
        monkeypatch.delenv(clave, raising=False)
    yield


def ganga(precio: float, hora: int = 6) -> Ganga:
    return Ganga(
        oferta=Oferta(
            fuente="ouigo",
            operador="Ouigo",
            origen_id="madrid_chamartin",
            origen_nombre="Madrid Chamartín",
            destino_id="elche_av",
            destino_nombre="Elche AV",
            fecha_salida=date(2026, 10, 1),
            hora_salida=time(hora, 15),
            hora_llegada=time(hora + 2, 37),
            duracion_min=142,
            precio_eur=precio,
            url_compra="https://ejemplo",
        ),
        motivo="Por debajo de 15 €.",
    )


def test_sin_secretos_no_envia_ni_falla():
    assert webpush.enviar("hola", "qué tal") == 0
    assert webpush.enviar_gangas([ganga(9.0)]) == 0


def test_sin_suscripcion_tampoco():
    """Tener las claves pero ningún móvil dado de alta no es un error."""
    import os

    os.environ["VAPID_CLAVE_PRIVADA"] = "loquesea"
    try:
        assert webpush.enviar("hola", "qué tal") == 0
    finally:
        del os.environ["VAPID_CLAVE_PRIVADA"]


def test_una_suscripcion_ilegible_no_tumba_el_resto(monkeypatch):
    monkeypatch.setenv("VAPID_CLAVE_PRIVADA", "clave")
    monkeypatch.setenv("WEB_PUSH_SUSCRIPCION", f"esto no es json\n{SUSCRIPCION}")

    enviados = []
    monkeypatch.setattr(
        "pywebpush.webpush", lambda **kw: enviados.append(kw["subscription_info"])
    )
    assert webpush.enviar("hola", "qué tal") == 1
    assert enviados[0]["endpoint"] == "https://push.example/abc"


def test_varios_dispositivos_uno_por_linea(monkeypatch):
    otra = SUSCRIPCION.replace("abc", "def")
    monkeypatch.setenv("VAPID_CLAVE_PRIVADA", "clave")
    monkeypatch.setenv("WEB_PUSH_SUSCRIPCION", f"{SUSCRIPCION}\n{otra}")
    monkeypatch.setattr("pywebpush.webpush", lambda **kw: None)

    assert webpush.enviar("hola", "qué tal") == 2


def test_con_varias_ofertas_manda_un_solo_aviso(monkeypatch):
    """Igual que en Telegram: una ráfaga de notificaciones no se lee."""
    monkeypatch.setenv("VAPID_CLAVE_PRIVADA", "clave")
    monkeypatch.setenv("WEB_PUSH_SUSCRIPCION", SUSCRIPCION)

    cargas = []
    monkeypatch.setattr("pywebpush.webpush", lambda **kw: cargas.append(kw["data"]))

    assert webpush.enviar_gangas([ganga(19.0), ganga(9.0, 8), ganga(30.0, 20)]) == 1
    aviso = json.loads(cargas[0])
    assert "3 ofertas" in aviso["titulo"]
    assert "9.00" in aviso["titulo"], "el titular lleva el precio más bajo"


def test_una_sola_oferta_va_con_su_detalle(monkeypatch):
    monkeypatch.setenv("VAPID_CLAVE_PRIVADA", "clave")
    monkeypatch.setenv("WEB_PUSH_SUSCRIPCION", SUSCRIPCION)

    cargas = []
    monkeypatch.setattr("pywebpush.webpush", lambda **kw: cargas.append(kw["data"]))

    webpush.enviar_gangas([ganga(9.0)])
    aviso = json.loads(cargas[0])
    assert "Elche AV" in aviso["cuerpo"]
    assert "jue 01/10" in aviso["cuerpo"], "la fecha, en español"


def test_los_canales_son_independientes(monkeypatch):
    """Que Telegram esté sin configurar no puede impedir el aviso del móvil."""
    monkeypatch.setenv("VAPID_CLAVE_PRIVADA", "clave")
    monkeypatch.setenv("WEB_PUSH_SUSCRIPCION", SUSCRIPCION)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr("pywebpush.webpush", lambda **kw: None)

    salidos = avisar_de_gangas([ganga(9.0)])
    assert salidos["telegram"] == 0
    assert salidos["webpush"] == 1
