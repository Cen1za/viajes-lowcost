"""Avisos como notificación del móvil, sin depender de Telegram.

La app instalada puede recibir notificaciones del sistema, pero Web Push exige
un servidor que las mande. Aquí no hay servidor, así que lo hace el propio
GitHub Actions con las claves guardadas como secretos:

    VAPID_CLAVE_PRIVADA   la mitad privada del par (`python -m buscador claves-push`)
    VAPID_ASUNTO          un mailto: o una URL de contacto, lo exige el estándar
    WEB_PUSH_SUSCRIPCION  lo que devuelve el móvil al dar permiso

**La suscripción va en un secreto y no en el repositorio a propósito**: aunque
parezca inofensiva, contiene un endpoint único que permite mandar
notificaciones a ese móvil, y este repositorio es público.

Se admiten varios dispositivos poniendo una suscripción por línea en el mismo
secreto. Si un endpoint deja de valer -pasa cuando se reinstala la app-, el
servidor de push responde 404 o 410: eso se avisa, pero no se considera un
fallo, porque no hay nada que arreglar salvo volver a dar permiso.
"""

from __future__ import annotations

import json
import logging
import os

from ..fechas import dia_corto

log = logging.getLogger(__name__)

#: Cuánto puede vivir el mensaje en el servidor de push si el móvil está
#: apagado. Un precio de tren caduca rápido: mejor que no llegue a que llegue
#: mañana anunciando una oferta que ya no existe.
CADUCIDAD_S = 6 * 3600


def _configuracion() -> tuple[str, str, list[dict]] | None:
    privada = os.environ.get("VAPID_CLAVE_PRIVADA", "").strip()
    asunto = os.environ.get("VAPID_ASUNTO", "").strip()
    crudo = os.environ.get("WEB_PUSH_SUSCRIPCION", "").strip()

    if not privada or not crudo:
        return None
    if not asunto:
        # El estándar pide una forma de contacto; si no se da, se usa una que
        # al menos identifica al proyecto en vez de fallar por un detalle.
        asunto = "mailto:avisos@viajes-lowcost.local"

    suscripciones = []
    for linea in crudo.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            suscripciones.append(json.loads(linea))
        except ValueError:
            log.warning("web push: una suscripción no es JSON válido, se ignora")

    return (privada, asunto, suscripciones) if suscripciones else None


def enviar(titulo: str, cuerpo: str, url: str = "/") -> int:
    """Manda una notificación a los móviles suscritos. Devuelve cuántas salieron."""
    ajustes = _configuracion()
    if ajustes is None:
        log.info("Web Push sin configurar: no se envía nada")
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        log.warning("web push: falta pywebpush (pip install pywebpush)")
        return 0

    privada, asunto, suscripciones = ajustes
    carga = json.dumps({"titulo": titulo, "cuerpo": cuerpo, "url": url})
    enviados = 0

    for suscripcion in suscripciones:
        try:
            webpush(
                subscription_info=suscripcion,
                data=carga,
                vapid_private_key=privada,
                vapid_claims={"sub": asunto},
                ttl=CADUCIDAD_S,
            )
            enviados += 1
        except WebPushException as error:
            respuesta = getattr(error, "response", None)
            codigo = getattr(respuesta, "status_code", None)
            if codigo in (404, 410):
                log.warning(
                    "web push: un dispositivo ya no acepta avisos (HTTP %s). "
                    "Vuelve a activarlos desde Ajustes y actualiza el secreto.",
                    codigo,
                )
            else:
                log.warning("web push: no se pudo enviar (%s)", error)
        except Exception as error:  # noqa: BLE001 - un aviso nunca tumba la ejecución
            log.warning("web push: error inesperado (%s)", error)

    return enviados


def enviar_gangas(gangas) -> int:
    """Mismo criterio que en Telegram: con varias, un solo aviso agrupado."""
    if not gangas:
        return 0

    mejores = sorted(gangas, key=lambda g: g.oferta.precio_eur)
    barata = mejores[0].oferta

    if len(mejores) == 1:
        titulo = f"{barata.precio_eur:.2f} € · {barata.operador}"
        cuerpo = (
            f"{barata.origen_nombre} → {barata.destino_nombre}\n"
            f"{dia_corto(barata.fecha_salida)} a las {barata.hora_salida:%H:%M}"
        )
    else:
        titulo = f"{len(mejores)} ofertas, desde {barata.precio_eur:.2f} €"
        cuerpo = (
            f"La mejor: {barata.origen_nombre} → {barata.destino_nombre}, "
            f"{dia_corto(barata.fecha_salida)} a las {barata.hora_salida:%H:%M}"
        )

    return enviar(titulo, cuerpo)
