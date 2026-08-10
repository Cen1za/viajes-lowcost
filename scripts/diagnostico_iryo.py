"""Abre iryo desde donde se ejecute y guarda lo que ve, sin buscar precios.

iryo funciona desde un PC de casa y devuelve cero desde GitHub Actions: falla
esperando `#ilsa-main-search-radio-outbound`, es decir, ese elemento no llega a
existir. Eso puede ser una página en blanco, un muro de Cloudflare o
simplemente una carga más lenta, y son tres arreglos distintos. Este script no
adivina: fotografía la página y vuelca su HTML para poder mirarlo.

Prueba las dos formas de arrancar el navegador —Chrome de verdad y el Chromium
que trae Playwright— porque justamente esa diferencia ya nos dio problemas una
vez con esta misma web.

Los resultados van a `diagnostico/`. En Actions se suben como artefacto.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

INICIO = "https://iryo.eu/es/home"
RADIO_SOLO_IDA = "#ilsa-main-search-radio-outbound"
SALIDA = Path("diagnostico")

#: Cuánto esperamos como mucho a que aparezca el formulario. El adaptador
#: espera 9 s a ciegas; aquí damos margen de sobra para distinguir "no carga"
#: de "carga lenta", que es una de las hipótesis.
ESPERA_MS = 45000


#: Las tres formas de arrancar el navegador que merece la pena comparar:
#: la que usa hoy el adaptador, la que ya sabemos que falla, y la candidata a
#: arreglarlo. Esta última pide una pantalla de verdad, que en Linux la da
#: `xvfb-run`; sin `DISPLAY` simplemente falla al arrancar y se anota.
VARIANTES: tuple[tuple[str, dict], ...] = (
    ("chrome-real", {"channel": "chrome", "headless": True}),
    ("chromium-playwright", {"headless": True}),
    ("chrome-con-pantalla", {"channel": "chrome", "headless": False}),
)


def mirar(navegador, etiqueta: str, user_agent: str) -> dict:
    contexto = navegador.new_context(
        locale="es-ES",
        timezone_id="Europe/Madrid",
        user_agent=user_agent,
        viewport={"width": 1450, "height": 1050},
    )
    contexto.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    pagina = contexto.new_page()
    informe: dict = {"variante": etiqueta}

    try:
        respuesta = pagina.goto(INICIO, timeout=90000, wait_until="domcontentloaded")
        informe["http"] = respuesta.status if respuesta else None

        # ¿Aparece el formulario si le damos tiempo de sobra?
        try:
            pagina.wait_for_selector(RADIO_SOLO_IDA, timeout=ESPERA_MS, state="attached")
            informe["formulario"] = "aparece"
        except Exception:
            informe["formulario"] = "NO aparece"

        pagina.wait_for_timeout(3000)
        informe["titulo"] = pagina.title()
        informe["url_final"] = pagina.url

        cuerpo = pagina.inner_text("body")
        informe["texto_visible_chars"] = len(cuerpo.strip())
        informe["primeras_lineas"] = [
            linea.strip() for linea in cuerpo.splitlines() if linea.strip()
        ][:25]

        html = pagina.content()
        informe["html_chars"] = len(html)
        # Las tres sospechas, en el orden en que las miraríamos a ojo.
        bajo = html.lower()
        informe["indicios"] = {
            "cloudflare": "cloudflare" in bajo or "cf-challenge" in bajo,
            "captcha": "captcha" in bajo or "turnstile" in bajo,
            "acceso_denegado": "access denied" in bajo or "forbidden" in bajo,
        }

        (SALIDA / f"{etiqueta}.html").write_text(html, encoding="utf-8")
        pagina.screenshot(path=str(SALIDA / f"{etiqueta}.png"), full_page=True)

    except Exception as error:  # noqa: BLE001 - es un diagnóstico, nada puede tumbarlo
        informe["fallo"] = f"{type(error).__name__}: {error}"
    finally:
        contexto.close()

    return informe


def main() -> int:
    # La consola de Windows va en cp1252 y se atraganta con los acentos.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    SALIDA.mkdir(exist_ok=True)
    agente = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    informes = []

    with sync_playwright() as pw:
        for etiqueta, opciones in VARIANTES:
            try:
                navegador = pw.chromium.launch(
                    args=["--disable-blink-features=AutomationControlled"],
                    **opciones,
                )
            except Exception as error:  # noqa: BLE001
                informes.append({"variante": etiqueta, "fallo_al_arrancar": str(error)})
                continue
            try:
                informes.append(mirar(navegador, etiqueta, agente))
            finally:
                navegador.close()

    (SALIDA / "informe.json").write_text(
        json.dumps(informes, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(informes, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
