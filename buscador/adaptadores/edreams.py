"""Adaptador de eDreams mediante navegador real.

eDreams **sí vende billetes de tren** (lo desmentí al principio y me equivoqué),
y además es la única fuente que agrega **AVE, Avlo, Alvia y Ouigo en una sola
consulta**. Eso la hace especialmente rentable: donde Renfe tarda 30 s en dar
sus trenes y Ouigo otros 3 s por su lado, aquí sale todo junto.

Tres cosas que costaron encontrar:

1. **Sí hay enlace profundo, pero no donde parecía.** `/trenes/madrid-elche/`
   devuelve 404; lo que funciona es la ruta de resultados con los parámetros
   en el *hash*, separados por `;` (ver `URL_RESULTADOS`). Cambiar ese hash
   relanza la búsqueda sin recargar la página. Es, de todas las fuentes, la
   única que permite enlazar a una búsqueda concreta.
2. **Hay que ir directo a los resultados.** Si se entra por la portada aparece
   un modal de login (`[data-testid=modal-backdrop]`) que tapa el formulario y
   el autocompletado. Navegando directamente a la URL de resultados no hay
   formulario que rellenar y el problema desaparece.
3. **Publica dos precios y solo uno es real.** Cada tren muestra el precio
   normal y, al lado y más grande, una "tarifa Prime" bastante más barata que
   exige suscribirse (29,99 €/trimestre tras 15 días de prueba). Guardar ese
   segundo número sería mentir en el histórico: aquí se toma siempre el
   **"Precio sin descuento"**. Ver `JS_EXTRAER`.

Ojo con lo que significan sus precios: eDreams es una agencia, así que puede
llevar comisión sobre lo que cobra el operador. Por eso cada oferta se guarda
con `fuente="edreams"` y la app enseña siempre de dónde sale cada precio.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, time, timedelta

from ..config import Config
from ..modelos import Consulta, Estacion, Oferta
from .base import AdaptadorBase, ErrorAdaptador, registrar

#: Búsqueda de ida suelta. Los parámetros van en el hash y separados por `;`,
#: no como query string normal. `type=O` es "one way".
URL_RESULTADOS = (
    "https://www.edreams.es/travel/trains/?step=departure"
    "#results/type=O;from={origen};to={destino};dep={fecha};adults=1;adultAges=30"
    ";buyPath=HOME_RAIL_TAB;internalSearch=true;trainSearch=true"
)

#: Identificadores de estación de eDreams. Salieron de la propia URL al elegir
#: cada estación en su buscador; su autocompletado (`/frontend-home/service/geo/
#: itinerary/autocomplete`) devuelve HTML si se le llama desde fuera de la web,
#: así que no sirve para redescubrirlos: si alguno cambia, hay que sacarlo otra
#: vez a mano.
#:
#: `nombre` es el texto con el que la propia web nombra la estación en los
#: resultados; se usa para descartar trenes que van a otra estación distinta
#: de la pedida (Alicante entra como ciudad, no como estación).
ESTACIONES: dict[str, tuple[str, str]] = {
    "madrid_atocha": ("1064946", "atocha"),
    "madrid_chamartin": ("1070286", "chamartin"),
    "elche_av": ("110190675", "elx alta velo"),
    "alicante": ("9629", "alicante t"),
}

#: Cómo llama eDreams a cada operador y cómo lo llamamos nosotros. El nombre
#: de la derecha es el que colorea las tarjetas de la app (ver web/src/companias.ts).
OPERADORES = {
    "AVE": "AVE",
    "AVLO": "Avlo",
    "OUIGO ES": "Ouigo",
    "OUIGO": "Ouigo",
    "ALVIA": "Alvia",
    "IRYO": "iryo",
}

ITINERARIO = '[data-testid="itinerary"]'

#: Saca de cada tarjeta los datos en crudo. Se trabaja sobre el texto visible
#: y no sobre clases CSS porque las clases de eDreams van ofuscadas y cambian
#: en cada despliegue; el texto ("Precio sin descuento", "· AVE", "2 h 33 min")
#: es mucho más estable.
#:
#: El precio se busca SIEMPRE tras "Precio sin descuento". Si esa etiqueta no
#: aparece es que la tarjeta no ofrece tarifa Prime y entonces solo hay un
#: precio, que ya es el bueno.
JS_EXTRAER = """
() => {
  const limpio = (t) => (t || '').replace(/\\u00a0/g, ' ').trim();
  return [...document.querySelectorAll('[data-testid="itinerary"]')].map(tarjeta => {
    const lineas = limpio(tarjeta.innerText).split('\\n').map(limpio).filter(Boolean);
    const texto = lineas.join('\\n');

    const operador = (texto.match(/^·\\s*(.+)$/m) || [])[1] || null;
    const horas = texto.match(/\\b([01]?\\d|2[0-3]):[0-5]\\d\\b/g) || [];
    const dur = texto.match(/(\\d+)\\s*h(?:\\s*(\\d+)\\s*min)?/);
    const estaciones = lineas.filter(l => /,/.test(l) && !/€/.test(l));

    let precio = (texto.match(/Precio sin descuento\\n([\\d.,]+)\\s*€/) || [])[1];
    if (!precio) precio = (texto.match(/([\\d.,]+)\\s*€/) || [])[1];

    return {
      operador,
      salida: horas[0] || null,
      llegada: horas[1] || null,
      duracion_min: dur ? parseInt(dur[1], 10) * 60 + parseInt(dur[2] || '0', 10) : null,
      origen: estaciones[0] || '',
      destino: estaciones[1] || '',
      precio: precio || null,
      directo: /\\bdirecto\\b/.test(texto),
    };
  });
}
"""


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar nombres de estación."""
    plano = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in plano if unicodedata.category(c) != "Mn").lower().strip()


def _a_precio(texto: str) -> float | None:
    """'1.234,56' y '45' -> float. Devuelve None si no hay número."""
    limpio = re.sub(r"[^\d.,]", "", texto or "")
    if not limpio:
        return None
    limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


class AdaptadorEdreams(AdaptadorBase):
    nombre = "edreams"

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._pw = None
        self._navegador = None
        self._contexto = None

    # -- Navegador ----------------------------------------------------------

    def _pagina(self):
        if self._contexto is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as error:
                raise ErrorAdaptador(
                    "edreams: falta Playwright. Instálalo con:\n"
                    "  pip install playwright && playwright install chrome"
                ) from error

            self._pw = sync_playwright().start()
            try:
                self._navegador = self._pw.chromium.launch(
                    headless=True,
                    channel="chrome",  # igual que iryo: Chrome de verdad
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except Exception as error:
                raise ErrorAdaptador(
                    "edreams: hace falta Chrome de verdad, no el navegador que trae "
                    "Playwright. Instálalo con:  playwright install chrome"
                ) from error

            self._contexto = self._navegador.new_context(
                locale="es-ES",
                timezone_id="Europe/Madrid",
                user_agent=self.config.red.user_agent,
                viewport={"width": 1450, "height": 1050},
            )
            self._contexto.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )
        return self._contexto.new_page()

    def cerrar(self) -> None:
        super().cerrar()
        for recurso, metodo in (
            (self._contexto, "close"),
            (self._navegador, "close"),
            (self._pw, "stop"),
        ):
            if recurso is not None:
                try:
                    getattr(recurso, metodo)()
                except Exception:  # noqa: BLE001
                    pass
        self._contexto = self._navegador = self._pw = None

    # -- Flujo --------------------------------------------------------------

    def _codigo(self, estacion: Estacion) -> tuple[str, str]:
        datos = ESTACIONES.get(estacion.id)
        if datos is None:
            raise ErrorAdaptador(f"edreams: no tengo el código de {estacion.nombre!r}")
        return datos

    def enlace(self, consulta: Consulta) -> str:
        """URL de la búsqueda en eDreams. A diferencia del resto de fuentes,
        esta sí lleva al listado con la ruta y el día ya puestos."""
        origen, _ = self._codigo(consulta.origen)
        destino, _ = self._codigo(consulta.destino)
        return URL_RESULTADOS.format(
            origen=origen, destino=destino, fecha=consulta.fecha.isoformat()
        )

    def _rechazar_cookies(self, pagina) -> None:
        for selector in (
            "#didomi-notice-disagree-button",
            "button:has-text('Rechazar')",
            "button:has-text('Continuar sin aceptar')",
        ):
            try:
                boton = pagina.locator(selector)
                if boton.count() and boton.first.is_visible():
                    boton.first.click(timeout=5000)
                    pagina.wait_for_timeout(1500)
                    return
            except Exception:  # noqa: BLE001
                continue

    def buscar(self, consulta: Consulta) -> list[Oferta]:
        url = self.enlace(consulta)
        pagina = self._pagina()
        try:
            pagina.goto(url, timeout=90000, wait_until="domcontentloaded")
            self._rechazar_cookies(pagina)
            try:
                pagina.wait_for_selector(ITINERARIO, timeout=45000)
            except Exception as error:  # noqa: BLE001
                # Sin trenes ese día es un resultado válido, no un fallo; lo
                # que no vale es confundirlo con la página a medio cargar.
                if "no hay" in _normalizar(pagina.inner_text("body")[:4000]):
                    return []
                raise ErrorAdaptador(
                    f"edreams: no aparecieron resultados para {consulta.fecha}"
                ) from error

            pagina.wait_for_timeout(2500)
            crudos = pagina.evaluate(JS_EXTRAER)
        finally:
            try:
                pagina.close()
            except Exception:  # noqa: BLE001
                pass

        if isinstance(crudos, str):  # por si evaluate devuelve JSON serializado
            crudos = json.loads(crudos)
        return self._a_ofertas(crudos or [], consulta, url)

    # -- Conversión ---------------------------------------------------------

    def _a_ofertas(self, crudos: list[dict], consulta: Consulta, url: str) -> list[Oferta]:
        _, destino_esperado = self._codigo(consulta.destino)
        ofertas: list[Oferta] = []
        vistos: set[tuple] = set()

        for crudo in crudos:
            try:
                salida = datetime.strptime(crudo["salida"], "%H:%M").time()
                llegada = datetime.strptime(crudo["llegada"], "%H:%M").time()
            except (TypeError, ValueError, KeyError):
                continue

            precio = _a_precio(crudo.get("precio") or "")
            if precio is None:
                continue

            # Alicante entra en eDreams como ciudad, no como estación: hay que
            # comprobar que el tren llega de verdad a la que pedimos.
            if destino_esperado not in _normalizar(crudo.get("destino") or ""):
                continue

            operador = OPERADORES.get(
                (crudo.get("operador") or "").strip().upper(),
                (crudo.get("operador") or "").strip() or "Tren",
            )

            clave = (operador, salida, llegada, precio)
            if clave in vistos:
                continue
            vistos.add(clave)

            ofertas.append(
                Oferta(
                    fuente=self.nombre,
                    operador=operador,
                    origen_id=consulta.origen.id,
                    origen_nombre=consulta.origen.nombre,
                    destino_id=consulta.destino.id,
                    destino_nombre=consulta.destino.nombre,
                    sentido=consulta.sentido,
                    fecha_salida=consulta.fecha,
                    hora_salida=salida,
                    hora_llegada=llegada,
                    duracion_min=crudo.get("duracion_min") or self._duracion(salida, llegada),
                    precio_eur=precio,
                    tarifa="eDreams",
                    url_compra=url,
                )
            )
        return ofertas

    @staticmethod
    def _duracion(salida: time, llegada: time) -> int:
        base = date(2000, 1, 1)
        inicio, fin = datetime.combine(base, salida), datetime.combine(base, llegada)
        if fin < inicio:
            fin += timedelta(days=1)
        return int((fin - inicio).total_seconds() // 60)


registrar("edreams", AdaptadorEdreams)
