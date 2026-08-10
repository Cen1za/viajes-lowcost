"""Contrato común de los adaptadores y el registro donde se dan de alta.

Regla de oro: un adaptador roto nunca puede tumbar la ejecución. `ejecutar()`
envuelve cada búsqueda, captura cualquier excepción y devuelve un
`ResultadoFuente` con el error para que quede registrado en estado_fuentes.json.
"""

from __future__ import annotations

import logging
import time as _time
from typing import Callable, Protocol

import httpx

from ..config import Config
from ..modelos import Consulta, Estacion, Oferta, ResultadoFuente

log = logging.getLogger(__name__)


class ErrorAdaptador(Exception):
    """Fallo esperable de una fuente (web caída, formato cambiado, sin códigos)."""


class Adaptador(Protocol):
    """Lo que tiene que implementar cualquier fuente de precios."""

    nombre: str

    def buscar(self, consulta: Consulta) -> list[Oferta]:
        """Devuelve las ofertas de esa fuente para ese trayecto y día."""
        ...

    def descubrir_estaciones(self, estaciones: list[Estacion]) -> dict[str, str]:
        """Devuelve {id_estacion: codigo_en_esta_fuente} para las que reconozca."""
        ...


class AdaptadorBase:
    """Base con el cliente HTTP y el ritmo de peticiones ya resueltos."""

    nombre: str = "base"

    def __init__(self, config: Config) -> None:
        self.config = config
        self._ultima_peticion = 0.0
        self._cliente: httpx.Client | None = None

    # -- HTTP ---------------------------------------------------------------

    @property
    def cliente(self) -> httpx.Client:
        if self._cliente is None:
            self._cliente = httpx.Client(
                timeout=self.config.red.timeout_s,
                follow_redirects=True,
                headers=self.cabeceras(),
            )
        return self._cliente

    def cabeceras(self) -> dict[str, str]:
        return {
            "User-Agent": self.config.red.user_agent,
            "Accept-Language": "es-ES,es;q=0.9",
        }

    def _esperar_turno(self) -> None:
        """Deja pasar la pausa configurada entre peticiones a la misma fuente."""
        pausa = self.config.red.pausa_entre_peticiones_s
        transcurrido = _time.monotonic() - self._ultima_peticion
        if self._ultima_peticion and transcurrido < pausa:
            _time.sleep(pausa - transcurrido)
        self._ultima_peticion = _time.monotonic()

    def peticion(self, metodo: str, url: str, **kwargs) -> httpx.Response:
        """Petición con ritmo, reintentos y errores traducidos a ErrorAdaptador."""
        ultimo_error: Exception | None = None
        for intento in range(self.config.red.reintentos + 1):
            self._esperar_turno()
            try:
                respuesta = self.cliente.request(metodo, url, **kwargs)
                respuesta.raise_for_status()
                return respuesta
            except httpx.HTTPStatusError as error:
                # 4xx que no sea 429 no se arregla reintentando.
                if error.response.status_code != 429 and error.response.status_code < 500:
                    raise ErrorAdaptador(
                        f"{self.nombre}: HTTP {error.response.status_code} en {url}"
                    ) from error
                ultimo_error = error
            except httpx.HTTPError as error:
                ultimo_error = error

            if intento < self.config.red.reintentos:
                espera = self.config.red.pausa_entre_peticiones_s * (intento + 2)
                log.debug("%s: reintento %d tras %.1fs", self.nombre, intento + 1, espera)
                _time.sleep(espera)

        raise ErrorAdaptador(f"{self.nombre}: sin respuesta de {url} ({ultimo_error})")

    def cerrar(self) -> None:
        if self._cliente is not None:
            self._cliente.close()
            self._cliente = None

    # -- Contrato -----------------------------------------------------------

    def buscar(self, consulta: Consulta) -> list[Oferta]:
        raise NotImplementedError

    def descubrir_estaciones(self, estaciones: list[Estacion]) -> dict[str, str]:
        return {}

    def codigo_o_error(self, estacion: Estacion) -> str:
        codigo = estacion.codigo(self.nombre)
        if not codigo:
            raise ErrorAdaptador(
                f"{self.nombre}: no tengo el código de {estacion.nombre!r}. "
                f"Ejecuta `python -m buscador estaciones` para descubrirlo."
            )
        return codigo


#: Límites de lo que es un precio y un viaje creíbles en esta ruta. No son
#: un capricho: raspar una web es leer números de un HTML que puede cambiar
#: sin avisar, y un extractor que empieza a coger la celda equivocada
#: devolvería basura con toda naturalidad. Un fallo total se ve enseguida
#: (cero ofertas); uno sutil, no. Esto lo caza.
PRECIO_MINIMO = 5.0
PRECIO_MAXIMO = 600.0
DURACION_MINIMA = 30      # minutos
DURACION_MAXIMA = 10 * 60


def validar(oferta: Oferta, consulta: Consulta) -> str | None:
    """Devuelve el motivo por el que una oferta no es creíble, o None si lo es."""
    if not PRECIO_MINIMO <= oferta.precio_eur <= PRECIO_MAXIMO:
        return f"precio fuera de rango: {oferta.precio_eur} €"
    if not DURACION_MINIMA <= oferta.duracion_min <= DURACION_MAXIMA:
        return f"duración imposible: {oferta.duracion_min} min"
    if oferta.fecha_salida != consulta.fecha:
        return f"fecha equivocada: pedida {consulta.fecha}, devuelta {oferta.fecha_salida}"
    if oferta.origen_id != consulta.origen.id or oferta.destino_id != consulta.destino.id:
        return "trayecto distinto del consultado"
    return None


def ejecutar(
    adaptador: Adaptador, consultas: list[Consulta]
) -> tuple[list[Oferta], ResultadoFuente]:
    """Lanza un adaptador sobre varias consultas sin que un fallo lo tumbe todo."""
    inicio = _time.monotonic()
    ofertas: list[Oferta] = []
    errores: list[str] = []
    descartadas = 0

    for consulta in consultas:
        try:
            encontradas = adaptador.buscar(consulta)
        except ErrorAdaptador as error:
            errores.append(str(error))
            log.warning("%s: %s", adaptador.nombre, error)
        except Exception as error:  # noqa: BLE001 - queremos capturarlo todo
            errores.append(f"{type(error).__name__}: {error}")
            log.exception("%s: fallo inesperado en %s", adaptador.nombre, consulta)
        else:
            creibles = []
            for oferta in encontradas:
                motivo = validar(oferta, consulta)
                if motivo:
                    descartadas += 1
                    log.warning("%s: descartada (%s) en %s", adaptador.nombre, motivo, consulta)
                    if len(errores) < 3:
                        errores.append(f"dato descartado: {motivo}")
                else:
                    creibles.append(oferta)
            ofertas.extend(creibles)
            log.info("%s: %d ofertas en %s", adaptador.nombre, len(creibles), consulta)

    duracion = _time.monotonic() - inicio
    # La fuente se considera sana si ha devuelto algo, aunque alguna consulta
    # suelta haya fallado. Solo se marca en rojo si no ha traído nada, o si ha
    # descartado más de lo que ha aceptado: eso significa que el extractor está
    # leyendo mal y no hay que fiarse de lo poco que haya salvado.
    ok = bool(ofertas) and descartadas <= len(ofertas)
    if not ofertas and not errores:
        ok = True  # simplemente no hay trenes ese día

    if descartadas:
        errores.append(f"{descartadas} datos no creíbles descartados")

    resultado = ResultadoFuente(
        fuente=adaptador.nombre,
        ok=ok,
        ofertas=len(ofertas),
        descartadas=descartadas,
        error=" | ".join(errores[:3]) if errores else None,
        duracion_s=round(duracion, 2),
    )
    return ofertas, resultado


#: Fábricas de adaptadores, indexadas por el nombre que usa config/app.yaml.
#: Cada módulo de adaptador se registra aquí al importarse desde __init__.
REGISTRO: dict[str, Callable[[Config], Adaptador]] = {}


def registrar(nombre: str, fabrica: Callable[[Config], Adaptador]) -> None:
    REGISTRO[nombre] = fabrica


def crear_adaptadores(config: Config) -> list[Adaptador]:
    """Instancia solo los adaptadores activos en la configuración."""
    adaptadores = []
    for nombre in config.fuentes_activas():
        fabrica = REGISTRO.get(nombre)
        if fabrica is None:
            log.warning("Fuente %r activada en app.yaml pero no implementada", nombre)
            continue
        adaptadores.append(fabrica(config))
    return adaptadores
