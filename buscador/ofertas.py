"""Detección de ofertas destacadas y control de avisos repetidos."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from .config import DIR_DATOS, Config
from .fechas import dia_largo
from .historico import Referencia
from .modelos import Oferta

RUTA_ALERTAS = DIR_DATOS / "alertas_enviadas.json"


class Ganga(BaseModel):
    """Una oferta que merece un aviso al móvil, con el porqué."""

    oferta: Oferta
    motivo: str
    mediana_eur: float | None = None
    caida_pct: float | None = None

    @property
    def clave(self) -> str:
        """Identifica el aviso para no repetirlo dentro de la ventana antispam."""
        semilla = (
            f"{self.oferta.ruta}|{self.oferta.fecha_salida}|{self.oferta.operador}"
            f"|{self.oferta.hora_salida:%H:%M}|{self.oferta.precio_eur:.2f}"
        )
        return hashlib.sha1(semilla.encode("utf-8")).hexdigest()[:16]

    def texto(self) -> str:
        o = self.oferta
        lineas = [
            f"🚄 {o.operador} · {o.precio_eur:.2f} €",
            f"{o.origen_nombre} → {o.destino_nombre}",
            f"{dia_largo(o.fecha_salida)} · {o.hora_salida:%H:%M} → {o.hora_llegada:%H:%M}"
            f" ({o.duracion_min // 60}h{o.duracion_min % 60:02d})",
            "",
            self.motivo,
        ]
        if o.plazas_restantes:
            lineas.append(f"Quedan {o.plazas_restantes} plazas.")
        lineas.append(f"\nComprar: {o.url_compra}")
        return "\n".join(lineas)


def detectar(ofertas: list[Oferta], referencia: Referencia, config: Config) -> list[Ganga]:
    """Devuelve las ofertas que se salen de lo normal para ese viaje.

    Criterio principal: caída significativa frente a la mediana histórica y
    además ser el precio más bajo visto últimamente. Mientras no haya histórico
    suficiente se cae a un umbral absoluto, para que la app sirva desde el
    primer día en vez de estar diez días muda.
    """
    ajustes = config.ofertas
    factor = 1 - ajustes.caida_minima_pct / 100
    gangas: list[Ganga] = []

    # Un solo aviso por viaje: el tren más barato de cada (ruta, fecha).
    mejores: dict[tuple[str, object], Oferta] = {}
    for oferta in ofertas:
        clave = (oferta.ruta, oferta.fecha_salida)
        actual = mejores.get(clave)
        if actual is None or oferta.precio_eur < actual.precio_eur:
            mejores[clave] = oferta

    for oferta in mejores.values():
        mediana, dias_con_datos = referencia.mediana(
            oferta.ruta, oferta.fecha_salida, ajustes.dias_historico
        )

        if mediana is not None and dias_con_datos >= ajustes.dias_minimos_historico:
            if oferta.precio_eur > mediana * factor:
                continue
            minimo = referencia.minimo_reciente(
                oferta.ruta, oferta.fecha_salida, ajustes.dias_minimo_reciente
            )
            # Solo es noticia si MEJORA lo ya visto. Si el precio simplemente se
            # mantiene en el mínimo, el antispam de 24 h dejaría de taparlo al
            # día siguiente y acabarías recibiendo el mismo aviso cada mañana.
            if minimo is not None and oferta.precio_eur >= minimo:
                continue
            caida = (mediana - oferta.precio_eur) / mediana * 100
            gangas.append(
                Ganga(
                    oferta=oferta,
                    motivo=(
                        f"Baja un {caida:.0f}% respecto a lo habitual "
                        f"({mediana:.2f} € de mediana en los últimos "
                        f"{ajustes.dias_historico} días)."
                    ),
                    mediana_eur=round(mediana, 2),
                    caida_pct=round(caida, 1),
                )
            )
        elif oferta.precio_eur <= ajustes.umbral_absoluto_eur:
            gangas.append(
                Ganga(
                    oferta=oferta,
                    motivo=(
                        f"Por debajo de {ajustes.umbral_absoluto_eur:.0f} €. "
                        f"(Aún sin histórico suficiente para comparar: "
                        f"{dias_con_datos} de {ajustes.dias_minimos_historico} días.)"
                    ),
                )
            )

    return sorted(gangas, key=lambda g: g.oferta.precio_eur)


# -- Antispam ---------------------------------------------------------------


def _cargar_enviadas() -> dict[str, str]:
    if not RUTA_ALERTAS.exists():
        return {}
    try:
        with RUTA_ALERTAS.open(encoding="utf-8") as fichero:
            return json.load(fichero)
    except (json.JSONDecodeError, OSError):
        return {}


def filtrar_repetidas(gangas: list[Ganga], horas: int) -> list[Ganga]:
    """Quita las que ya se avisaron dentro de la ventana antispam."""
    enviadas = _cargar_enviadas()
    corte = datetime.now(timezone.utc) - timedelta(hours=horas)

    nuevas = []
    for ganga in gangas:
        marca = enviadas.get(ganga.clave)
        if marca:
            try:
                if datetime.fromisoformat(marca) > corte:
                    continue
            except ValueError:
                pass
        nuevas.append(ganga)
    return nuevas


def registrar_enviadas(gangas: list[Ganga], horas: int) -> None:
    """Anota las alertas enviadas y limpia las que ya han caducado."""
    enviadas = _cargar_enviadas()
    ahora = datetime.now(timezone.utc)
    corte = ahora - timedelta(hours=horas * 2)

    vigentes = {}
    for clave, marca in enviadas.items():
        try:
            if datetime.fromisoformat(marca) > corte:
                vigentes[clave] = marca
        except ValueError:
            continue

    for ganga in gangas:
        vigentes[ganga.clave] = ahora.isoformat(timespec="seconds")

    RUTA_ALERTAS.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_ALERTAS.open("w", encoding="utf-8") as fichero:
        json.dump(vigentes, fichero, ensure_ascii=False, indent=2, sort_keys=True)
        fichero.write("\n")
