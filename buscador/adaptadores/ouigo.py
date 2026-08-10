"""Adaptador de Ouigo España.

Ouigo expone una API JSON limpia (la que usa su propio buscador web):

    POST /api/Token/login        credenciales públicas del cliente web
    POST /api/Sale/journeysearch trenes y precios de un día concreto
    POST /api/Calendar/prices    precio mínimo por día en un rango

La API no publica un listado de estaciones, así que el catálogo va incrustado
más abajo. Se obtuvo del buscador de ouigo.com y se verificó contra la propia
API (journeysearch devuelve el nombre de la estación de llegada).
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime, timedelta

from ..config import Config
from ..modelos import Consulta, Estacion, Oferta
from .base import AdaptadorBase, ErrorAdaptador, registrar

BASE = "https://mdw02.api-es.ouigo.com/api"

#: Credenciales del cliente web público de Ouigo. No son secretas: cualquier
#: navegador que abra ouigo.com hace exactamente esta misma llamada.
USUARIO_WEB = "ouigo.web"
CLAVE_WEB = "SquirelWeb!2020"

#: Catálogo de estaciones de Ouigo España: código UIC -> alias reconocibles.
CATALOGO: dict[str, tuple[str, ...]] = {
    "7160000": ("madrid puerta de atocha", "madrid atocha", "atocha"),
    "7117000": ("madrid chamartin", "chamartin", "madrid chamartin clara campoamor"),
    "7103410": ("elche", "elx", "elche av", "elx av"),
    "7160911": ("alicante", "alicante terminal"),
    "7161200": ("murcia", "murcia del carmen"),
    "7160600": ("albacete", "albacete los llanos"),
    "7171801": ("barcelona", "barcelona sants"),
    "7103216": ("valencia", "valencia joaquin sorolla"),
    "7104040": ("zaragoza", "zaragoza delicias"),
    "7151003": ("sevilla", "sevilla santa justa"),
    "7150500": ("cordoba", "cordoba julio anguita"),
    "7154413": ("malaga", "malaga maria zambrano"),
    "7104104": ("tarragona", "camp de tarragona"),
    "7110600": ("valladolid", "valladolid campo grande"),
    "7108004": ("segovia", "segovia guiomar"),
    "7103208": ("cuenca", "cuenca fernando zobel"),
}

#: Un pasajero adulto sin descuentos ni necesidades de accesibilidad.
PASAJERO_ADULTO = {"discount_cards": [], "disability_type": "NH", "type": "A"}


def _normalizar(texto: str) -> str:
    """Minúsculas sin acentos ni signos, para comparar nombres de estación."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.lower().replace("-", " ").split())


class AdaptadorOuigo(AdaptadorBase):
    nombre = "ouigo"

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._token: str | None = None

    # -- Autenticación ------------------------------------------------------

    def _autenticar(self) -> str:
        if self._token:
            return self._token
        respuesta = self.peticion(
            "POST",
            f"{BASE}/Token/login",
            json={"username": USUARIO_WEB, "password": CLAVE_WEB},
        )
        token = respuesta.json().get("token")
        if not token:
            raise ErrorAdaptador("ouigo: el login no ha devuelto token")
        self._token = token
        return token

    def _cabeceras_auth(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._autenticar()}",
            "Content-Type": "application/json",
        }

    def _pasajeros(self, consulta: Consulta) -> list[dict]:
        return [dict(PASAJERO_ADULTO) for _ in range(max(1, consulta.adultos))]

    # -- Estaciones ---------------------------------------------------------

    def descubrir_estaciones(self, estaciones: list[Estacion]) -> dict[str, str]:
        """Casa los nombres de config/app.yaml con el catálogo de Ouigo."""
        encontrados: dict[str, str] = {}
        for estacion in estaciones:
            objetivo = _normalizar(estacion.nombre)
            for codigo, alias in CATALOGO.items():
                if objetivo in alias or any(a in objetivo for a in alias):
                    encontrados[estacion.id] = codigo
                    break
        return encontrados

    # -- Búsqueda -----------------------------------------------------------

    def buscar(self, consulta: Consulta) -> list[Oferta]:
        origen = self.codigo_o_error(consulta.origen)
        destino = self.codigo_o_error(consulta.destino)

        respuesta = self.peticion(
            "POST",
            f"{BASE}/Sale/journeysearch",
            headers=self._cabeceras_auth(),
            json={
                "origin": origen,
                "destination": destino,
                "outbound_date": consulta.fecha.isoformat(),
                "passengers": self._pasajeros(consulta),
            },
        )

        datos = respuesta.json() or {}
        if datos.get("error"):
            raise ErrorAdaptador(f"ouigo: {datos['error']}")

        ofertas = []
        for viaje in datos.get("outbound") or []:
            oferta = self._a_oferta(viaje, consulta)
            if oferta is not None:
                ofertas.append(oferta)
        return ofertas

    def _a_oferta(self, viaje: dict, consulta: Consulta) -> Oferta | None:
        precio = viaje.get("price")
        if precio is None:
            return None  # tren sin plazas a la venta

        salida = viaje.get("departure_station") or {}
        llegada = viaje.get("arrival_station") or {}
        try:
            hora_salida = datetime.fromisoformat(salida["departure_timestamp"])
            hora_llegada = datetime.fromisoformat(llegada["arrival_timestamp"])
        except (KeyError, TypeError, ValueError):
            return None

        tarifa = "Promo" if viaje.get("is_promo") else "Básica"
        if viaje.get("full"):
            return None

        return Oferta(
            fuente=self.nombre,
            operador="Ouigo",
            # Usamos el nombre corto de config/app.yaml, no el larguísimo de la
            # fuente ("Madrid - Chamartín - Clara Campoamor"), para que las
            # tablas y los avisos de Telegram se lean bien.
            origen_id=consulta.origen.id,
            origen_nombre=consulta.origen.nombre,
            destino_id=consulta.destino.id,
            destino_nombre=consulta.destino.nombre,
            sentido=consulta.sentido,
            fecha_salida=hora_salida.date(),
            hora_salida=hora_salida.time(),
            hora_llegada=hora_llegada.time(),
            duracion_min=int((hora_llegada - hora_salida).total_seconds() // 60),
            precio_eur=float(precio),
            tarifa=tarifa,
            plazas_restantes=viaje.get("remaining_seats"),
            url_compra="https://www.ouigo.com/es/",
        )

    # -- Calendario ---------------------------------------------------------

    def calendario(
        self, origen: Estacion, destino: Estacion, desde: date, hasta: date
    ) -> dict[date, float]:
        """Precio mínimo por día en un rango, con una sola petición.

        Es muchísimo más barato que pedir los trenes día a día, así que el modo
        calendario lo usa para decidir qué días merece la pena mirar en detalle.
        Ouigo limita el rango, así que se trocea de 30 en 30 días.
        """
        codigo_origen = self.codigo_o_error(origen)
        codigo_destino = self.codigo_o_error(destino)

        precios: dict[date, float] = {}
        inicio = desde
        while inicio <= hasta:
            fin = min(inicio + timedelta(days=29), hasta)
            respuesta = self.peticion(
                "POST",
                f"{BASE}/Calendar/prices",
                headers=self._cabeceras_auth(),
                json={
                    "direction": "outbound",
                    "begin": inicio.isoformat(),
                    "end": fin.isoformat(),
                    "origin": codigo_origen,
                    "destination": codigo_destino,
                    "passengers": [dict(PASAJERO_ADULTO)],
                },
            )
            for dia in respuesta.json() or []:
                if dia.get("price") is not None:
                    precios[date.fromisoformat(dia["date"])] = float(dia["price"])
            inicio = fin + timedelta(days=1)

        return precios


registrar("ouigo", AdaptadorOuigo)
