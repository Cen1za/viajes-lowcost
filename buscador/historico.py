"""Histórico de precios en ficheros JSONL, uno por mes.

Se guarda en texto plano y no en una base de datos a propósito: el repositorio
es la infraestructura, GitHub Actions hace commit de estos ficheros en cada
ejecución y los diffs siguen siendo legibles.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import DIR_DATOS
from .modelos import Oferta

DIR_HISTORICO = DIR_DATOS / "historico"


def _fichero(momento: date) -> Path:
    return DIR_HISTORICO / f"{momento:%Y-%m}.jsonl"


def guardar(ofertas: list[Oferta]) -> int:
    """Añade las ofertas al fichero del mes en que se capturaron."""
    if not ofertas:
        return 0

    DIR_HISTORICO.mkdir(parents=True, exist_ok=True)
    por_mes: dict[Path, list[Oferta]] = defaultdict(list)
    for oferta in ofertas:
        por_mes[_fichero(oferta.capturado_en.date())].append(oferta)

    escritas = 0
    for ruta, lote in por_mes.items():
        with ruta.open("a", encoding="utf-8") as fichero:
            for oferta in lote:
                fichero.write(oferta.model_dump_json() + "\n")
                escritas += 1
    return escritas


def cargar(desde: date | None = None) -> list[Oferta]:
    """Lee el histórico completo, o solo el capturado a partir de una fecha."""
    if not DIR_HISTORICO.exists():
        return []

    ofertas: list[Oferta] = []
    for ruta in sorted(DIR_HISTORICO.glob("*.jsonl")):
        if desde and ruta.stem < f"{desde:%Y-%m}":
            continue
        with ruta.open(encoding="utf-8") as fichero:
            for linea in fichero:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    oferta = Oferta.model_validate_json(linea)
                except Exception:  # noqa: BLE001 - una línea corrupta no rompe el resto
                    continue
                if desde is None or oferta.capturado_en.date() >= desde:
                    ofertas.append(oferta)
    return ofertas


def minimos_diarios(ofertas: list[Oferta]) -> dict[tuple[str, date], dict[date, float]]:
    """Precio mínimo observado cada día de captura, por ruta y fecha de viaje.

    Se agrupa así para que la mediana refleje "lo que suele costar ese viaje" y
    no se distorsione porque un día concreto se capturaran veinte trenes y otro
    día solo tres.
    """
    agrupado: dict[tuple[str, date], dict[date, float]] = defaultdict(dict)
    for oferta in ofertas:
        clave = (oferta.ruta, oferta.fecha_salida)
        dia = oferta.capturado_en.date()
        actual = agrupado[clave].get(dia)
        if actual is None or oferta.precio_eur < actual:
            agrupado[clave][dia] = oferta.precio_eur
    return agrupado


class Referencia:
    """Precios de referencia calculados sobre el histórico."""

    def __init__(self, ofertas: list[Oferta]) -> None:
        self._minimos = minimos_diarios(ofertas)

    def mediana(self, ruta: str, fecha_viaje: date, dias: int) -> tuple[float | None, int]:
        """Mediana de los mínimos diarios y número de días con datos."""
        por_dia = self._minimos.get((ruta, fecha_viaje))
        if not por_dia:
            return None, 0

        corte = datetime.now(timezone.utc).date() - timedelta(days=dias)
        valores = [precio for dia, precio in por_dia.items() if dia >= corte]
        if not valores:
            return None, 0
        return statistics.median(valores), len(valores)

    def minimo_reciente(self, ruta: str, fecha_viaje: date, dias: int) -> float | None:
        """Precio más bajo visto para ese viaje en los últimos `dias` días."""
        por_dia = self._minimos.get((ruta, fecha_viaje))
        if not por_dia:
            return None
        corte = datetime.now(timezone.utc).date() - timedelta(days=dias)
        valores = [precio for dia, precio in por_dia.items() if dia >= corte]
        return min(valores) if valores else None


def escribir_json(ruta: Path, datos) -> None:
    """Vuelca un JSON con formato estable, para que los diffs sean legibles."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as fichero:
        json.dump(datos, fichero, ensure_ascii=False, indent=2, default=str)
        fichero.write("\n")
