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

from ..fechas import dia_corto

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


#: A partir de aquí se manda un resumen en vez de un mensaje por oferta. Con
#: una o dos, el mensaje completo con horarios y enlace es lo más cómodo; con
#: treinta y dos -que es lo que salió el primer día- son treinta y dos
#: notificaciones seguidas, y a la tercera se silencia el bot.
AVISOS_SUELTOS = 2

#: Cuántas ofertas se detallan dentro del resumen. El resto se cuenta al final:
#: quien quiera verlas las tiene todas en la app.
EN_EL_RESUMEN = 8


def _resumen(gangas) -> str:
    """Un solo mensaje con las mejores ofertas, de más barata a menos."""
    mejores = sorted(gangas, key=lambda g: g.oferta.precio_eur)
    lineas = [f"🚄 <b>{len(gangas)} ofertas destacadas</b>", ""]

    for ganga in mejores[:EN_EL_RESUMEN]:
        o = ganga.oferta
        lineas.append(
            f"<b>{o.precio_eur:.2f} €</b> · {dia_corto(o.fecha_salida)} "
            f"{o.hora_salida:%H:%M} · {o.operador}"
        )
        lineas.append(f"   {o.origen_nombre} → {o.destino_nombre}")

    if len(mejores) > EN_EL_RESUMEN:
        lineas.append("")
        lineas.append(f"…y {len(mejores) - EN_EL_RESUMEN} más en la app.")

    return "\n".join(lineas)


def enviar_gangas(gangas) -> int:
    """Avisa de las ofertas destacadas. Devuelve cuántos mensajes se enviaron.

    Con pocas ofertas va una a una, con todo el detalle. En cuanto son varias
    se agrupan en un único mensaje: el objetivo es que el aviso se lea, y una
    ráfaga de notificaciones consigue justo lo contrario.
    """
    if not gangas:
        return 0
    if _credenciales() is None:
        log.info("Telegram sin configurar: %d ofertas no avisadas", len(gangas))
        return 0

    if len(gangas) > AVISOS_SUELTOS:
        return 1 if enviar_mensaje(_resumen(gangas)) else 0

    enviados = 0
    for ganga in gangas:
        if enviar_mensaje(ganga.texto()):
            enviados += 1
    return enviados
