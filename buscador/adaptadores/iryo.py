"""Adaptador de iryo mediante navegador real.

Dos cosas que costaron encontrar y conviene no volver a perder:

1. **Hay que usar Chrome de verdad** (`channel="chrome"`). Con el navegador
   headless que trae Playwright, iryo devuelve la página en blanco: carga el
   título y nada más. Con Chrome real en modo headless funciona con normalidad.
2. **Su API no sirve.** `api.iryo.eu` existe y responde, pero exige una clave
   de Azure API Management que la propia web resuelve en tiempo de ejecución y
   no está en su código. Se intentó y es un callejón sin salida; el camino
   bueno es rellenar el buscador, como haría una persona.

A cambio, su formulario es de los más limpios: las fechas son `input[type=date]`
nativos, así que se rellenan directamente sin pelearse con ningún calendario.

ESTADO: a medias, y por eso está desactivado en config/app.yaml.

Ya funciona: cargar la web, rechazar cookies, marcar "solo ida" y abrir el
desplegable de estaciones. Lo que falta es **leer las opciones de ese
desplegable**: no aparecen bajo `li`, `[role=option]` ni `.ilsa-dropdown__item`.
El siguiente paso es abrirlo con Chrome real y volcar el HTML del contenedor
que se despliega para ver qué etiqueta usan sus componentes `ilsa-*`.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta

from ..config import Config
from ..enlaces import web_operador
from ..modelos import Consulta, Estacion, Oferta
from .base import AdaptadorBase, ErrorAdaptador, registrar

INICIO = "https://iryo.eu/es/home"

#: Texto que se escribe en cada desplegable y patrón que debe casar la opción.
BUSQUEDAS: dict[str, tuple[str, str]] = {
    "madrid_atocha": ("Madrid", r"ATOCHA"),
    "madrid_chamartin": ("Madrid", r"CHAMART"),
    "elche_av": ("Elche", r"ELCHE|ELX"),
    "alicante": ("Alicante", r"ALICANTE|ALACANT"),
    "murcia": ("Murcia", r"MURCIA"),
}

ORIGEN = "#ilsa-main-search-select-route-dropdown-origin"
DESTINO = "#ilsa-main-search-select-route-dropdown-destination"
SOLO_IDA = "#ilsa-main-search-radio-outbound"

#: Extrae los trenes de la página de resultados. Igual que en Renfe, se buscan
#: los bloques que contienen precio, dos horas y una duración, en vez de
#: depender de unas clases CSS que cambian con cada rediseño.
JS_EXTRAER = r"""
() => {
  const RE_PRECIO = /(\d{1,3}[.,]\d{2})\s*€/;
  const RE_HORA = /\b([01]?\d|2[0-3]):([0-5]\d)\b/g;
  const RE_DURACION = /(\d+)\s*h(?:\s*(\d+)\s*m)?/i;

  const candidatos = new Set();
  for (const el of document.querySelectorAll('div, li, article, section, tr')) {
    const t = el.innerText || '';
    if (t.length > 700 || !RE_PRECIO.test(t)) continue;
    RE_HORA.lastIndex = 0;
    if ((t.match(RE_HORA) || []).length >= 2) candidatos.add(el);
  }
  const hojas = [...candidatos].filter(
    el => ![...candidatos].some(o => o !== el && el.contains(o))
  );

  return hojas.map(el => {
    const t = el.innerText.replace(/\s+/g, ' ').trim();
    RE_HORA.lastIndex = 0;
    const horas = [...t.matchAll(RE_HORA)].map(m => `${m[1].padStart(2,'0')}:${m[2]}`);
    const dur = t.match(RE_DURACION);
    const precios = [...t.matchAll(/(\d{1,3}[.,]\d{2})\s*€/g)]
      .map(m => parseFloat(m[1].replace(',', '.')));
    return {
      salida: horas[0] || null,
      llegada: horas[1] || null,
      duracion_min: dur ? (parseInt(dur[1],10)*60 + parseInt(dur[2] || '0',10)) : null,
      precio: precios.length ? Math.min(...precios) : null,
    };
  }).filter(x => x.salida && x.llegada && x.precio);
}
"""


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.upper().replace("-", " ").replace("/", " ").split())


class AdaptadorIryo(AdaptadorBase):
    nombre = "iryo"

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
                    "iryo: falta Playwright. Instálalo con:\n"
                    "  pip install playwright && playwright install chrome"
                ) from error

            self._pw = sync_playwright().start()
            try:
                self._navegador = self._pw.chromium.launch(
                    headless=True,
                    channel="chrome",  # imprescindible, ver la cabecera
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except Exception as error:
                raise ErrorAdaptador(
                    "iryo: hace falta Chrome de verdad, no el navegador que trae "
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

    def _preparar(self, pagina) -> None:
        pagina.goto(INICIO, timeout=90000, wait_until="domcontentloaded")
        pagina.wait_for_timeout(9000)
        for selector in ("button:has-text('RECHAZAR TODAS')", "button:has-text('Rechazar')"):
            try:
                boton = pagina.locator(selector)
                if boton.count() and boton.first.is_visible():
                    boton.first.click(timeout=6000)
                    pagina.wait_for_timeout(2500)
                    return
            except Exception:
                continue

    def _elegir_estacion(self, pagina, selector: str, estacion: Estacion) -> str | None:
        termino, patron = BUSQUEDAS.get(
            estacion.id, (estacion.nombre.split()[0], re.escape(_normalizar(estacion.nombre)))
        )
        # El input de verdad está oculto dentro de un componente desplegable:
        # hay que abrir el contenedor visible y solo entonces se puede escribir.
        campo = pagina.locator(selector).first
        etiqueta = "Origen" if "origin" in selector else "Destino"
        for abridor in (
            lambda: pagina.get_by_text(etiqueta, exact=True).first.click(timeout=8000),
            lambda: campo.locator("xpath=ancestor::*[self::div][1]").click(timeout=8000),
            lambda: campo.click(timeout=8000, force=True),
        ):
            try:
                abridor()
                pagina.wait_for_timeout(1200)
                break
            except Exception:
                continue

        try:
            campo.fill(termino, timeout=8000)
        except Exception:
            pagina.keyboard.type(termino, delay=60)
        pagina.wait_for_timeout(2500)

        opciones = pagina.locator("li, [role=option], .ilsa-dropdown__item")
        for i in range(min(opciones.count(), 30)):
            try:
                etiqueta = opciones.nth(i).inner_text().strip()
            except Exception:
                continue
            if etiqueta and re.search(patron, _normalizar(etiqueta), re.I):
                opciones.nth(i).click()
                pagina.wait_for_timeout(1500)
                return etiqueta
        return None

    def buscar(self, consulta: Consulta) -> list[Oferta]:
        pagina = self._pagina()
        try:
            self._preparar(pagina)

            # Solo ida: si no, pide también fecha de vuelta y no busca.
            try:
                pagina.locator(f"label[for='{SOLO_IDA.lstrip('#')}']").first.click(timeout=8000)
            except Exception:
                pagina.locator(SOLO_IDA).first.check(timeout=8000, force=True)
            pagina.wait_for_timeout(1500)

            if not self._elegir_estacion(pagina, ORIGEN, consulta.origen):
                raise ErrorAdaptador(f"iryo: no encuentro el origen {consulta.origen.nombre!r}")
            if not self._elegir_estacion(pagina, DESTINO, consulta.destino):
                raise ErrorAdaptador(f"iryo: no encuentro el destino {consulta.destino.nombre!r}")

            # Las fechas son input[type=date] nativos: se rellenan y ya.
            fechas = pagina.locator("input[type=date]")
            if not fechas.count():
                raise ErrorAdaptador("iryo: no encuentro el campo de fecha")
            fechas.first.fill(consulta.fecha.isoformat())
            pagina.wait_for_timeout(1200)

            pagina.locator("button:has-text('BUSCAR')").first.click(timeout=15000)
            pagina.wait_for_timeout(12000)

            return self._a_ofertas(pagina.evaluate(JS_EXTRAER), consulta)
        finally:
            pagina.close()

    # -- Normalización ------------------------------------------------------

    def _a_ofertas(self, crudos: list[dict], consulta: Consulta) -> list[Oferta]:
        ofertas = []
        for crudo in crudos:
            try:
                salida = datetime.strptime(crudo["salida"], "%H:%M").time()
                llegada = datetime.strptime(crudo["llegada"], "%H:%M").time()
            except (TypeError, ValueError):
                continue

            ofertas.append(
                Oferta(
                    fuente=self.nombre,
                    operador="iryo",
                    origen_id=consulta.origen.id,
                    origen_nombre=consulta.origen.nombre,
                    destino_id=consulta.destino.id,
                    destino_nombre=consulta.destino.nombre,
                    sentido=consulta.sentido,
                    fecha_salida=consulta.fecha,
                    hora_salida=salida,
                    hora_llegada=llegada,
                    duracion_min=crudo.get("duracion_min") or self._duracion(salida, llegada),
                    precio_eur=float(crudo["precio"]),
                    tarifa="Inicial",
                    url_compra=web_operador("iryo"),
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


registrar("iryo", AdaptadorIryo)
