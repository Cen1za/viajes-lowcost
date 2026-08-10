"""Adaptadores de fuentes de precios.

Importar este paquete registra en `base.REGISTRO` todos los adaptadores
disponibles. Los que todavía no estén implementados simplemente no aparecen,
y `crear_adaptadores` avisa si están activados en app.yaml.
"""

from .base import (  # noqa: F401
    Adaptador,
    AdaptadorBase,
    ErrorAdaptador,
    REGISTRO,
    crear_adaptadores,
    ejecutar,
    registrar,
)
from . import edreams  # noqa: F401 - se registra al importarse
from . import iryo  # noqa: F401 - se registra al importarse
from . import ouigo  # noqa: F401 - se registra al importarse
from . import renfe  # noqa: F401 - se registra al importarse

__all__ = [
    "Adaptador",
    "AdaptadorBase",
    "ErrorAdaptador",
    "REGISTRO",
    "crear_adaptadores",
    "ejecutar",
    "registrar",
]
