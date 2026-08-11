"""Carga de config/app.yaml y config/vigilancias.yaml."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .modelos import Estacion

RAIZ = Path(__file__).resolve().parent.parent
DIR_CONFIG = RAIZ / "config"
DIR_DATOS = RAIZ / "data"

#: Códigos de estación descubiertos automáticamente por el comando `estaciones`.
#: Se guardan aparte para no reescribir el fichero de configuración del usuario.
RUTA_CODIGOS = DIR_CONFIG / "estaciones_codigos.yaml"

DIAS_SEMANA = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}


class Pasajeros(BaseModel):
    adultos: int = 1
    descuentos: list[str] = Field(default_factory=list)
    #: Tu edad. Solo se usa para descartar las campañas que piden una edad que
    #: no tienes (las de 18-30, las de menores). Déjala en null para verlas
    #: todas. Ver `promociones.aplicables`.
    edad: int | None = None


class Busqueda(BaseModel):
    horizonte_dias: int = 90
    incluir_vuelta: bool = True
    dias_ida: list[str] = Field(default_factory=list)
    dias_vuelta: list[str] = Field(default_factory=list)
    #: Compatibilidad con configuraciones anteriores: si está puesto y no hay
    #: dias_ida, se usa para la ida.
    dias_semana: list[str] = Field(default_factory=list)
    hora_min: time | None = None
    hora_max: time | None = None

    @staticmethod
    def _indices(nombres: list[str]) -> set[int] | None:
        """Traduce nombres de días a índices de weekday(). None = todos valen."""
        if not nombres:
            return None
        indices = set()
        for nombre in nombres:
            clave = nombre.strip().lower()
            if clave not in DIAS_SEMANA:
                raise ValueError(
                    f"Día de la semana no reconocido en app.yaml: {nombre!r}. "
                    f"Valores válidos: {', '.join(sorted(set(DIAS_SEMANA)))}"
                )
            indices.add(DIAS_SEMANA[clave])
        return indices

    def indices_dias_semana(self, sentido: str = "ida") -> set[int] | None:
        """Días permitidos para ese sentido del viaje.

        La ida y la vuelta se configuran por separado a propósito: si sales
        viernes o sábado, las vueltas que te interesan son domingo y lunes, y
        con una sola lista no habría forma de expresarlo.
        """
        if sentido == "vuelta":
            return self._indices(self.dias_vuelta)
        return self._indices(self.dias_ida or self.dias_semana)


class Ofertas(BaseModel):
    caida_minima_pct: float = 25.0
    dias_historico: int = 30
    dias_minimo_reciente: int = 14
    dias_minimos_historico: int = 10
    umbral_absoluto_eur: float = 25.0
    antispam_horas: int = 24


class Red(BaseModel):
    timeout_s: float = 30.0
    pausa_entre_peticiones_s: float = 3.0
    reintentos: int = 2
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )


class Estaciones(BaseModel):
    origen: list[Estacion]
    destino: list[Estacion]

    def todas(self) -> list[Estacion]:
        return [*self.origen, *self.destino]

    def por_id(self, id_estacion: str) -> Estacion:
        for estacion in self.todas():
            if estacion.id == id_estacion:
                return estacion
        conocidas = ", ".join(e.id for e in self.todas())
        raise KeyError(f"Estación desconocida: {id_estacion!r}. Definidas: {conocidas}")


class Config(BaseModel):
    pasajeros: Pasajeros = Field(default_factory=Pasajeros)
    busqueda: Busqueda = Field(default_factory=Busqueda)
    estaciones: Estaciones
    ofertas: Ofertas = Field(default_factory=Ofertas)
    red: Red = Field(default_factory=Red)
    fuentes: dict[str, bool] = Field(default_factory=dict)

    def fuentes_activas(self) -> list[str]:
        return [nombre for nombre, activa in self.fuentes.items() if activa]


class Vigilancia(BaseModel):
    nombre: str
    origen: str
    destino: str
    ida: date
    vuelta: date | None = None
    precio_objetivo_eur: float | None = None


def _leer_yaml(ruta: Path) -> dict:
    if not ruta.exists():
        raise FileNotFoundError(f"No encuentro el fichero de configuración: {ruta}")
    with ruta.open(encoding="utf-8") as fichero:
        return yaml.safe_load(fichero) or {}


def cargar_config(ruta: Path | None = None) -> Config:
    """Lee app.yaml y le fusiona los códigos de estación ya descubiertos."""
    datos = _leer_yaml(ruta or DIR_CONFIG / "app.yaml")
    config = Config.model_validate(datos)

    if RUTA_CODIGOS.exists():
        codigos = _leer_yaml(RUTA_CODIGOS)
        for estacion in config.estaciones.todas():
            estacion.codigos.update(codigos.get(estacion.id, {}))

    # Validamos aquí los días de la semana para que un error en el YAML salte
    # al arrancar y no a mitad de un barrido de 90 días.
    config.busqueda.indices_dias_semana("ida")
    config.busqueda.indices_dias_semana("vuelta")
    return config


def cargar_vigilancias(ruta: Path | None = None) -> list[Vigilancia]:
    datos = _leer_yaml(ruta or DIR_CONFIG / "vigilancias.yaml")
    return [Vigilancia.model_validate(v) for v in (datos.get("vigilancias") or [])]


def guardar_codigos(codigos: dict[str, dict[str, str]]) -> None:
    """Guarda (fusionando) los códigos de estación descubiertos por fuente."""
    existentes: dict[str, dict[str, str]] = {}
    if RUTA_CODIGOS.exists():
        existentes = _leer_yaml(RUTA_CODIGOS)

    for id_estacion, por_fuente in codigos.items():
        existentes.setdefault(id_estacion, {}).update(por_fuente)

    RUTA_CODIGOS.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_CODIGOS.open("w", encoding="utf-8") as fichero:
        fichero.write("# Generado por `python -m buscador estaciones`. No editar a mano.\n")
        yaml.safe_dump(existentes, fichero, allow_unicode=True, sort_keys=True)
