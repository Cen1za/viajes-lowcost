"""Adaptador de iryo mediante navegador real.

Dos cosas que costaron encontrar y conviene no volver a perder:

1. **Hay que usar Chrome de verdad** (`channel="chrome"`). Con el navegador
   headless que trae Playwright, iryo devuelve la página en blanco: carga el
   título y nada más. Con Chrome real en modo headless funciona con normalidad.
2. **Su API no sirve.** `api.iryo.eu` existe y responde, pero exige una clave
   de Azure API Management que la propia web resuelve en tiempo de ejecución y
   no está en su código. Se intentó y es un callejón sin salida; el camino
   bueno es rellenar el buscador, como haría una persona.

3. **La fecha hay que picarla en su calendario.** Los `input[type=date]` que
   hay detrás son de solo lectura para nosotros: escribirles el valor por JS
   los deja con la fecha puesta pero Angular no se entera, el formulario nunca
   se da por válido y el botón BUSCAR se queda deshabilitado. Igual que en
   Renfe, hay que abrir el calendario y hacer un clic REAL de ratón sobre la
   celda del día. Ver `_fijar_fecha`.

Y ojo antes de invertir más: **iryo no llega a Elche ni a Murcia**. Sus 15
estaciones incluyen Alicante Terminal, así que aquí solo aporta precios de
Madrid ⇄ Alicante, con los 25 minutos de traslado hasta Elche.
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

#: Estaciones que iryo vende, con el patrón que identifica su opción.
#: OJO: iryo **no llega a Elche ni a Murcia**. En esta ruta solo aporta
#: precios de Madrid ⇄ Alicante, con los 25 minutos de traslado hasta Elche.
BUSQUEDAS: dict[str, str] = {
    "madrid_atocha": r"MADRID ATOCHA",
    "madrid_chamartin": r"MADRID CHAMARTIN",
    "alicante": r"ALICANTE",
}

ORIGEN = "#ilsa-main-search-select-route-dropdown-origin"
DESTINO = "#ilsa-main-search-select-route-dropdown-destination"
SOLO_IDA = "#ilsa-main-search-radio-outbound"

#: Calendario de la fecha de ida: el input visible que lo abre y la flecha
#: que avanza al mes siguiente. Ambos se localizan por data-qa.
#: Cuánto se espera a que aparezca el formulario. Antes eran 9 segundos fijos:
#: de más cuando la web va fina y de menos cuando va lenta.
ESPERA_FORMULARIO_MS = 30000

FECHA_IDA = '[data-qa="ilsa-main-search-datepicker__button-tmpStartDateRef"]'
MES_SIGUIENTE = '[data-qa="ilsa-main-search-datepicker__right-arrow"]'

#: Marca la celda del día pedido con un atributo propio y devuelve qué pasó.
#: No hace clic: el clic tiene que ser un evento real de ratón de Playwright,
#: porque un .click() desde JS no actualiza el modelo de Angular.
#: Las celdas no llevan ninguna fecha en el DOM, así que hay que cruzar el
#: mes del encabezado (data-qa con el mes en base 0) con el número del día.
JS_MARCAR_DIA = """
([anio, mes, dia]) => {
  for (const previa of document.querySelectorAll('[data-dia-objetivo]'))
    previa.removeAttribute('data-dia-objetivo');
  const calendario = [...document.querySelectorAll('.ilsa-datepicker__calendar')].find(c => {
    const cabecera = c.querySelector('.ilsa-datepicker__label');
    return cabecera && (cabecera.dataset.qa || '').includes(`month:${mes - 1}__year:${anio}`);
  });
  if (!calendario) return 'mes-no-visible';
  const celda = [...calendario.querySelectorAll('.ilsa-datepicker__monthdays-item--filled')]
    .filter(c => !c.className.includes('--disabled'))
    .find(c => (c.textContent || '').trim() === String(dia));
  if (!celda) return 'dia-no-disponible';
  celda.setAttribute('data-dia-objetivo', '1');
  return 'ok';
}
"""

#: Las opciones del desplegable. El contenedor se identifica por data-qa, no
#: por id: cuesta un rato darse cuenta porque el atributo se llama igual.
def _menu(selector: str) -> str:
    campo = selector.lstrip("#")
    return f'[data-qa="{campo}-menu"] .menu__item'

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
        #: Motivo por el que iryo no sirve la página aquí, si se ha demostrado.
        #: Se rellena en la primera consulta que falle y corta las siguientes.
        self._inservible: str | None = None

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

        # Esperar a que exista el formulario, en vez de contar 9 segundos a
        # ciegas: así no se penaliza cuando carga rápido ni se da por perdida
        # una carga lenta. Si no aparece, la página no es la que esperamos y no
        # tiene sentido seguir; ver la nota de `_inservible`.
        try:
            pagina.wait_for_selector(SOLO_IDA, timeout=ESPERA_FORMULARIO_MS, state="attached")
        except Exception as error:  # noqa: BLE001
            self._inservible = self._porque_no_carga(pagina)
            raise ErrorAdaptador(f"iryo: {self._inservible}") from error

        for selector in ("button:has-text('RECHAZAR TODAS')", "button:has-text('Rechazar')"):
            try:
                boton = pagina.locator(selector)
                if boton.count() and boton.first.is_visible():
                    boton.first.click(timeout=6000)
                    pagina.wait_for_timeout(2500)
                    return
            except Exception:
                continue

    @staticmethod
    def _porque_no_carga(pagina) -> str:
        """Describe en una línea qué se recibió, para no depurar a ciegas."""
        try:
            texto = pagina.inner_text("body").strip()
        except Exception:  # noqa: BLE001
            texto = ""
        if not texto:
            return (
                "la página llega en blanco. Es lo que hace iryo cuando no le "
                "convence el navegador; hace falta Chrome de verdad "
                "(playwright install chrome), y aun así puede rechazar "
                "servidores. Ver scripts/diagnostico_iryo.py"
            )
        return f"no aparece el formulario, pero sí {len(texto)} caracteres de texto"

    def _elegir_estacion(self, pagina, selector: str, estacion: Estacion) -> str | None:
        patron = BUSQUEDAS.get(estacion.id)
        if patron is None:
            raise ErrorAdaptador(
                f"iryo no llega a {estacion.nombre}. Solo opera "
                f"{', '.join(BUSQUEDAS)} en esta zona."
            )

        # El input real está oculto: se abre el desplegable pinchando su
        # contenedor y se elige de la lista, sin escribir.
        pagina.locator(
            f"{selector} >> xpath=ancestor::div[contains(@class,'ilsa-dropdown')][1]"
        ).first.click(timeout=20000)
        pagina.wait_for_timeout(2000)

        opciones = pagina.locator(_menu(selector))
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
        # Si la primera consulta demostró que aquí iryo no sirve la página, las
        # siguientes van a fallar igual. Reintentarlas costaba seis minutos y
        # medio por ejecución, cuatro veces al día, para nada.
        if self._inservible:
            raise ErrorAdaptador(f"iryo: {self._inservible} (no se reintenta)")

        pagina = self._pagina()
        try:
            self._preparar(pagina)

            # Solo ida: si no, pide también fecha de vuelta y no busca.
            # El radio está tapado por su decoración, de ahí el force.
            pagina.locator(SOLO_IDA).first.click(timeout=10000, force=True)
            pagina.wait_for_timeout(1500)

            if not self._elegir_estacion(pagina, ORIGEN, consulta.origen):
                raise ErrorAdaptador(f"iryo: no encuentro el origen {consulta.origen.nombre!r}")
            if not self._elegir_estacion(pagina, DESTINO, consulta.destino):
                raise ErrorAdaptador(f"iryo: no encuentro el destino {consulta.destino.nombre!r}")

            self._fijar_fecha(pagina, consulta.fecha)

            pagina.locator("button:has-text('BUSCAR')").first.click(timeout=15000)
            pagina.wait_for_timeout(12000)

            return self._a_ofertas(pagina.evaluate(JS_EXTRAER), consulta)
        finally:
            pagina.close()

    def _fijar_fecha(self, pagina, fecha: date) -> None:
        """Elige la fecha de ida picándola en el calendario de iryo.

        Inyectar el valor en el `input[type=date]` por JS no vale: el campo se
        queda con la fecha bien puesta, pero Angular no lo registra y el botón
        BUSCAR nunca se habilita. Como en Renfe, hace falta un clic real de
        ratón sobre la celda del día.
        """
        pagina.locator(FECHA_IDA).first.click(timeout=20000)
        pagina.wait_for_timeout(2500)

        # El calendario abre en el mes actual y solo enseña uno cada vez.
        estado = "mes-no-visible"
        for _ in range(14):
            estado = pagina.evaluate(JS_MARCAR_DIA, [fecha.year, fecha.month, fecha.day])
            if estado != "mes-no-visible":
                break
            pagina.locator(MES_SIGUIENTE).first.click(timeout=10000)
            pagina.wait_for_timeout(900)

        if estado != "ok":
            raise ErrorAdaptador(f"iryo: el calendario no ofrece el día {fecha} ({estado})")

        pagina.locator("[data-dia-objetivo]").first.click(timeout=10000)
        pagina.wait_for_timeout(2500)

        # Comprobamos lo que ha recogido el formulario antes de buscar, para no
        # guardar nunca precios de un día que no es el pedido.
        aplicada = pagina.locator(FECHA_IDA).first.input_value()
        if aplicada != f"{fecha:%d/%m/%Y}":
            raise ErrorAdaptador(
                f"iryo: la fecha no se aplicó (formulario={aplicada!r}, pedida={fecha:%d/%m/%Y})"
            )

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
