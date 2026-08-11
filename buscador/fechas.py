"""Fechas escritas en español, sin depender del idioma de la máquina.

`%A` y `%a` de strftime usan el idioma del sistema, así que los avisos salían
en inglés ("Thu 01/10") al mandarse desde GitHub, que corre en inglés, y en
español al probarlos en casa. Como el mensaje lo lee una persona y siempre en
español, aquí se escriben los nombres a mano y se acabó la sorpresa.
"""

from __future__ import annotations

from datetime import date

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def dia_corto(fecha: date) -> str:
    """'jue 01/10'"""
    return f"{DIAS_CORTOS[fecha.weekday()]} {fecha:%d/%m}"


def dia_largo(fecha: date) -> str:
    """'jueves 1 de octubre de 2026'"""
    return (
        f"{DIAS[fecha.weekday()]} {fecha.day} de "
        f"{MESES[fecha.month - 1]} de {fecha.year}"
    )
