"""Canales de aviso al móvil."""

from .telegram import enviar_gangas, enviar_mensaje  # noqa: F401

__all__ = ["enviar_gangas", "enviar_mensaje"]
