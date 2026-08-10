"""Avisos por Telegram.

Necesita dos variables de entorno (en GitHub van como Secrets):

    TELEGRAM_BOT_TOKEN   el que te da @BotFather al crear el bot
    TELEGRAM_CHAT_ID     tu id de usuario, te lo dice @userinfobot

Si faltan, el envío se salta sin romper la ejecución: la búsqueda y el
histórico siguen funcionando igual.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/sendMessage"
LIMITE_TELEGRAM = 4000  # el máximo real son 4096 caracteres


def _credenciales() -> tuple[str, str] | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return None
    return token, chat


def enviar_mensaje(texto: str) -> bool:
    """Envía un mensaje. Devuelve False si no hay credenciales o falla el envío."""
    credenciales = _credenciales()
    if credenciales is None:
        log.info("Telegram sin configurar (faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID)")
        return False

    token, chat = credenciales
    try:
        respuesta = httpx.post(
            API.format(token=token),
            json={
                "chat_id": chat,
                "text": texto[:LIMITE_TELEGRAM],
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as error:
        log.warning("Telegram: no se pudo enviar el aviso (%s)", error)
        return False
    return True


def enviar_gangas(gangas) -> int:
    """Un mensaje por oferta destacada. Devuelve cuántos se enviaron."""
    if not gangas:
        return 0
    if _credenciales() is None:
        log.info("Telegram sin configurar: %d ofertas no avisadas", len(gangas))
        return 0

    enviados = 0
    for ganga in gangas:
        if enviar_mensaje(ganga.texto()):
            enviados += 1
    return enviados
