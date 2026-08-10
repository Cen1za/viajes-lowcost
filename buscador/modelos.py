"""Modelos de datos compartidos por todos los adaptadores.

La idea central: cada fuente (Trainline, Ouigo, Renfe...) devuelve sus datos en
un formato distinto, pero todas los traducen a `Oferta`. A partir de ahí el resto
del programa no necesita saber de dónde vino cada precio.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from pydantic import BaseModel, Field


class Estacion(BaseModel):
    """Una estación tal y como la define el usuario en config/app.yaml."""

    id: str
    nombre: str
    principal: bool = False
    #: Minutos extra de traslado hasta el destino real (Elche centro).
    traslado_min: int = 0
    nota: str | None = None
    #: Identificador de esta estación en cada fuente. Se rellena con el comando
    #: `estaciones`, porque cada web usa su propia codificación.
    codigos: dict[str, str] = Field(default_factory=dict)

    def codigo(self, fuente: str) -> str | None:
        return self.codigos.get(fuente)


class Consulta(BaseModel):
    """Una búsqueda concreta: un trayecto en un día concreto."""

    origen: Estacion
    destino: Estacion
    fecha: date
    adultos: int = 1
    #: "ida" (Madrid → Elche) o "vuelta" (Elche → Madrid).
    sentido: str = "ida"

    def __str__(self) -> str:
        return f"{self.origen.nombre} → {self.destino.nombre} el {self.fecha:%d/%m/%Y}"


class Oferta(BaseModel):
    """Un tren concreto con su precio en una fuente concreta."""

    fuente: str
    operador: str

    origen_id: str
    origen_nombre: str
    destino_id: str
    destino_nombre: str
    #: "ida" o "vuelta". Permite que la app las presente por separado.
    sentido: str = "ida"

    fecha_salida: date
    hora_salida: time
    hora_llegada: time
    duracion_min: int

    precio_eur: float
    tarifa: str | None = None
    plazas_restantes: int | None = None

    #: Enlace a la lista de trenes de ese día. Ni Renfe ni Ouigo permiten
    #: enlazar a un billete concreto, así que apunta a la búsqueda equivalente
    #: en Trainline, que sí acepta trayecto y fecha en la URL.
    url_compra: str
    #: Portada del operador, para comprar sin intermediario.
    url_operador: str | None = None
    capturado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0)
    )

    @property
    def clave_tren(self) -> str:
        """Identifica el tren físico, con independencia de dónde se venda.

        Sirve para colapsar en una sola fila el mismo tren visto en Trainline,
        en Omio y en la web del operador, quedándonos con el precio más bajo.
        """
        return (
            f"{self.operador}|{self.origen_id}|{self.destino_id}"
            f"|{self.fecha_salida.isoformat()}|{self.hora_salida:%H:%M}"
        )

    @property
    def ruta(self) -> str:
        return f"{self.origen_id}->{self.destino_id}"

    def resumen(self) -> str:
        return (
            f"{self.fecha_salida:%d/%m} {self.operador} "
            f"{self.hora_salida:%H:%M}→{self.hora_llegada:%H:%M} "
            f"{self.destino_nombre} · {self.precio_eur:.2f}€ ({self.fuente})"
        )


class ResultadoFuente(BaseModel):
    """Cómo le ha ido a un adaptador en una ejecución.

    Se vuelca a data/estado_fuentes.json para que la PWA muestre qué fuentes
    están sanas y para avisar cuando una lleva varios fallos seguidos.
    """

    fuente: str
    ok: bool
    ofertas: int = 0
    error: str | None = None
    duracion_s: float = 0.0
    ejecutado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0)
    )
