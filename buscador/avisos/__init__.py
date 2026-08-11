"""Canales de aviso al móvil.

Hay dos y son independientes a propósito: Telegram llega a cualquier sitio y no
depende del navegador, y Web Push avisa en el móvil aunque no tengas Telegram.
Cada uno se activa por su cuenta según los secretos que haya configurados, y
que uno falle no impide que el otro salga.
"""

from . import webpush  # noqa: F401
from .telegram import enviar_gangas, enviar_mensaje  # noqa: F401


def avisar_de_gangas(gangas) -> dict[str, int]:
    """Manda las ofertas por todos los canales configurados.

    Devuelve cuántos avisos ha soltado cada uno, para poder decir en la salida
    del comando si alguno estaba sin configurar.
    """
    return {
        "telegram": enviar_gangas(gangas),
        "webpush": webpush.enviar_gangas(gangas),
    }


__all__ = ["avisar_de_gangas", "enviar_gangas", "enviar_mensaje", "webpush"]
