"""Adaptador de Renfe (AVE y Avlo) mediante navegador real.

Renfe no expone una API de precios y sus peticiones directas están protegidas,
pero la web funciona con normalidad desde un navegador. El flujo replicado aquí
es exactamente el de un usuario, y es el orden lo que importa:

    1. rechazar las cookies no esenciales
    2. elegir origen y destino en el autocompletado
    3. abrir el calendario  (el selector ida / ida y vuelta vive DENTRO de él)
    4. marcar "solo ida"
    5. hacer clic REAL sobre el día (un .click() de JS no lo registra)
    6. Aceptar y buscar

Es la fuente más lenta y más frágil del proyecto: si Renfe cambia su web hay
que retocar los selectores de este fichero y solo de este fichero.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta

from ..config import Config
from ..modelos import Consulta, Estacion, Oferta
from .base import AdaptadorBase, ErrorAdaptador, registrar

INICIO = "https://www.renfe.com/es/es"

#: Términos que se escriben en el autocompletado y patrón que debe casar la
#: opción correcta. Los patrones se comparan contra la etiqueta ya normalizada
#: (mayúsculas, sin acentos y con guiones y barras convertidos en espacios),
#: así que aquí van con espacios: "ATOCHA ALMUDENA", no "ATOCHA-ALMUDENA".
BUSQUEDAS: dict[str, tuple[str, str]] = {
    "madrid_atocha": ("MADRID", r"ATOCHA ALMUDENA"),
    "madrid_chamartin": ("MADRID", r"CHAMART"),
    "elche_av": ("ELCHE", r"ELX AV"),
    "alicante": ("ALICANTE", r"ALACANT TERMINAL"),
    "murcia": ("MURCIA", r"DEL CARMEN"),
}

#: Localiza en el calendario la celda del día pedido y devuelve su data-time.
#: No hace clic: el clic tiene que ser un evento real de ratón de Playwright.
JS_BUSCAR_DIA = """
([a, m, d]) => {
  const celda = [...document.querySelectorAll('.lightpick__day[data-time]')]
    .filter(c => !c.classList.contains('is-disabled'))
    .find(c => {
      const f = new Date(Number(c.dataset.time));
      return f.getFullYear() === a && f.getMonth() === m - 1 && f.getDate() === d;
    });
  return celda ? celda.dataset.time : null;
}
"""

#: Extrae los trenes de la página de resultados. En lugar de depender de las
#: clases CSS de Renfe (que cambian), busca los bloques que contienen un precio
#: y sube al ancestro que además tenga las dos horas y la duración.
JS_EXTRAER = r"""
() => {
  const RE_PRECIO = /(\d{1,3},\d{2})\s*€/;
  const RE_HORA = /\b([01]?\d|2[0-3]):([0-5]\d)\s*h/g;
  const RE_DURACION = /(\d+)\s*horas?\s*(?:(\d+)\s*minutos?)?/i;

  const candidatos = new Set();
  for (const el of document.querySelectorAll('div, li, tr, article, section')) {
    const t = el.innerText || '';
    if (!RE_PRECIO.test(t)) continue;
    if (t.length > 900) continue;
    RE_HORA.lastIndex = 0;
    const horas = t.match(RE_HORA) || [];
    if (horas.length >= 2 && RE_DURACION.test(t)) candidatos.add(el);
  }

  // Nos quedamos con los bloques más internos (sin descendientes candidatos)
  const hojas = [...candidatos].filter(
    el => ![...candidatos].some(otro => otro !== el && el.contains(otro))
  );

  return hojas.map(el => {
    const t = el.innerText.replace(/\s+/g, ' ').trim();
    RE_HORA.lastIndex = 0;
    const horas = [...t.matchAll(RE_HORA)].map(m => `${m[1].padStart(2,'0')}:${m[2]}`);
    const dur = t.match(RE_DURACION);
    const precios = [...t.matchAll(/(\d{1,3},\d{2})\s*€/g)].map(m => parseFloat(m[1].replace(',', '.')));
    const tipo = (t.match(/\b(AVLO|AVE|ALVIA|EUROMED|INTERCITY|AVANT|MD)\b/i) || [])[1] || null;
    return {
      salida: horas[0] || null,
      llegada: horas[1] || null,
      duracion_min: dur ? (parseInt(dur[1], 10) * 60 + parseInt(dur[2] || '0', 10)) : null,
      precio: precios.length ? Math.min(...precios) : null,
      tipo,
      texto: t.slice(0, 200),
    };
  }).filter(x => x.salida && x.llegada && x.precio);
}
"""


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.upper().replace("-", " ").replace("/", " ").split())


class AdaptadorRenfe(AdaptadorBase):
    nombre = "renfe"

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._pw = None
        self._navegador = None
        self._contexto = None

    # -- Navegador ----------------------------------------------------------

    def _pagina(self):
        """Abre el navegador la primera vez y lo reutiliza para todas las consultas."""
        if self._contexto is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as error:
                raise ErrorAdaptador(
                    "renfe: falta Playwright. Instálalo con:\n"
                    "  pip install playwright && playwright install chromium"
                ) from error

            self._pw = sync_playwright().start()
            self._navegador = self._pw.chromium.launch(headless=True)
            self._contexto = self._navegador.new_context(
                locale="es-ES",
                timezone_id="Europe/Madrid",
                user_agent=self.config.red.user_agent,
                viewport={"width": 1500, "height": 1100},
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
                except Exception:  # noqa: BLE001 - cerrar nunca debe romper
                    pass
        self._contexto = self._navegador = self._pw = None

    # -- Estaciones ---------------------------------------------------------

    def descubrir_estaciones(self, estaciones: list[Estacion]) -> dict[str, str]:
        """Guarda la etiqueta exacta que usa el autocompletado de Renfe."""
        pendientes = [e for e in estaciones if e.id in BUSQUEDAS]
        if not pendientes:
            return {}

        pagina = self._pagina()
        try:
            self._preparar(pagina)
            encontradas = {}
            for estacion in pendientes:
                termino, patron = BUSQUEDAS[estacion.id]
                etiqueta = self._autocompletar(pagina, "destination", termino, patron)
                if etiqueta:
                    encontradas[estacion.id] = etiqueta
            return encontradas
        finally:
            pagina.close()

    # -- Flujo de la web ----------------------------------------------------

    def _preparar(self, pagina) -> None:
        pagina.goto(INICIO, timeout=90000, wait_until="domcontentloaded")
        pagina.wait_for_timeout(3000)
        # Rechazamos las cookies no esenciales, nunca las aceptamos todas.
        try:
            pagina.locator("#onetrust-reject-all-handler").click(timeout=8000)
            pagina.wait_for_timeout(1200)
        except Exception:
            pass  # a veces no aparece el banner

    def _autocompletar(self, pagina, campo: str, termino: str, patron: str) -> str | None:
        pagina.locator(f"#{campo}").first.click(timeout=20000)
        pagina.locator(f"#{campo}").first.fill(termino)
        pagina.wait_for_timeout(2500)
        lista = pagina.locator(f"#{campo}-awe li")
        for i in range(lista.count()):
            etiqueta = lista.nth(i).inner_text().strip()
            if re.search(patron, _normalizar(etiqueta), re.I):
                lista.nth(i).click()
                pagina.wait_for_timeout(1000)
                return etiqueta
        return None

    def _patron(self, estacion: Estacion) -> tuple[str, str]:
        """Término a escribir y patrón a casar para una estación de config."""
        if estacion.id in BUSQUEDAS:
            return BUSQUEDAS[estacion.id]
        # Estación no prevista: usamos su propio nombre como término y patrón.
        nombre = _normalizar(estacion.nombre)
        return nombre.split()[0], re.escape(nombre)

    def buscar(self, consulta: Consulta) -> list[Oferta]:
        pagina = self._pagina()
        try:
            self._preparar(pagina)

            termino, patron = self._patron(consulta.origen)
            if not self._autocompletar(pagina, "origin", termino, patron):
                raise ErrorAdaptador(f"renfe: no encuentro el origen {consulta.origen.nombre!r}")

            termino, patron = self._patron(consulta.destino)
            if not self._autocompletar(pagina, "destination", termino, patron):
                raise ErrorAdaptador(f"renfe: no encuentro el destino {consulta.destino.nombre!r}")

            self._fijar_fecha(pagina, consulta.fecha)

            pagina.locator("#ticketSearchBt").first.click(timeout=20000)
            try:
                pagina.wait_for_url("**/vol/**", timeout=90000)
            except Exception as error:
                raise ErrorAdaptador("renfe: la búsqueda no llegó a la página de resultados") from error
            pagina.wait_for_timeout(9000)

            crudos = pagina.evaluate(JS_EXTRAER)
            return self._a_ofertas(crudos, consulta, pagina.url)
        finally:
            pagina.close()

    def _fijar_fecha(self, pagina, fecha: date) -> None:
        pagina.locator("#first-input").first.click(timeout=20000)
        pagina.wait_for_timeout(2500)

        # El selector ida / ida y vuelta está dentro del panel del calendario.
        try:
            pagina.locator("label[for='trip-go']").first.click(timeout=10000)
            pagina.wait_for_timeout(1200)
        except Exception:
            pass

        marca = None
        for _ in range(14):
            marca = pagina.evaluate(JS_BUSCAR_DIA, [fecha.year, fecha.month, fecha.day])
            if marca:
                break
            pagina.locator(".lightpick__next-action").first.click()
            pagina.wait_for_timeout(700)

        if not marca:
            raise ErrorAdaptador(f"renfe: el calendario no ofrece el día {fecha}")

        # Clic real de ratón: lightpick ignora los .click() lanzados desde JS.
        pagina.locator(f'.lightpick__day[data-time="{marca}"]').first.click(timeout=10000)
        pagina.wait_for_timeout(1500)

        try:
            aceptar = pagina.locator(".lightpick__apply-action-sub", has_text="Aceptar")
            if aceptar.count() and aceptar.first.is_visible():
                aceptar.first.click(timeout=6000)
                pagina.wait_for_timeout(1500)
        except Exception:
            pass

        # Comprobamos que el formulario ha recogido la fecha; si no, abortamos
        # antes de buscar para no guardar precios del día equivocado.
        aplicada = pagina.evaluate(
            "() => (document.getElementsByName('FechaIdaSel')[0] || {}).value || ''"
        )
        if aplicada != f"{fecha:%d/%m/%Y}":
            raise ErrorAdaptador(
                f"renfe: la fecha no se aplicó (formulario={aplicada!r}, pedida={fecha:%d/%m/%Y})"
            )

    # -- Normalización ------------------------------------------------------

    def _a_ofertas(self, crudos: list[dict], consulta: Consulta, url: str) -> list[Oferta]:
        ofertas = []
        for crudo in crudos:
            try:
                salida = datetime.strptime(crudo["salida"], "%H:%M").time()
                llegada = datetime.strptime(crudo["llegada"], "%H:%M").time()
            except (TypeError, ValueError):
                continue

            duracion = crudo.get("duracion_min") or self._duracion(salida, llegada)
            operador = (crudo.get("tipo") or "").upper()
            operador = {"AVLO": "Avlo", "AVE": "AVE"}.get(operador, "Renfe")

            ofertas.append(
                Oferta(
                    fuente=self.nombre,
                    operador=operador,
                    origen_id=consulta.origen.id,
                    origen_nombre=consulta.origen.nombre,
                    destino_id=consulta.destino.id,
                    destino_nombre=consulta.destino.nombre,
                    fecha_salida=consulta.fecha,
                    hora_salida=salida,
                    hora_llegada=llegada,
                    duracion_min=duracion,
                    precio_eur=float(crudo["precio"]),
                    tarifa="Precio desde",
                    url_compra=url,
                )
            )
        return ofertas

    @staticmethod
    def _duracion(salida: time, llegada: time) -> int:
        base = date(2000, 1, 1)
        inicio = datetime.combine(base, salida)
        fin = datetime.combine(base, llegada)
        if fin < inicio:  # llega pasada la medianoche
            fin += timedelta(days=1)
        return int((fin - inicio).total_seconds() // 60)


registrar("renfe", AdaptadorRenfe)
