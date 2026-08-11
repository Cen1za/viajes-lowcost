"""Vigila las campañas que anuncian Renfe y Ouigo en su portada.

Esto **no** son precios de trenes: es lo que las compañías están promocionando
ahora mismo, que es otra cosa y por eso vive fuera del sistema de ofertas.

Dos decisiones que vienen de mirar cómo son esas páginas de verdad:

1. **No se lee su página de "ofertas y promociones".** La de Ouigo es un
   archivo que nadie limpia: en agosto de 2026 seguía anunciando los Pink Days
   que caducaron en enero de 2025, una promo que acabó en septiembre de 2024 y
   otra de las Fallas de 2023. Raspar eso llenaría el móvil de campañas
   muertas. Lo que sí está vivo es lo que destacan en la portada.

2. **Solo se avisa cuando CAMBIA.** Una lista de promociones repetida cada día
   es ruido, y el ruido acaba en que no se lee ninguna. Se guarda una huella de
   lo que hay y solo se dice algo cuando aparece una campaña nueva, que es el
   momento en que sirve de algo.

Ojo con las expectativas: las campañas suelen ir dirigidas a perfiles concretos
(18-30 años, grupos de 4 a 9, menores) y a un adulto viajando solo no le suele
aplicar ninguna. El valor está en enterarse el mismo día si sacan una que sí.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

import httpx

log = logging.getLogger(__name__)

#: Portadas de cada compañía. Se leen con una petición normal, sin navegador:
#: el texto de las campañas viaja en el HTML.
PORTADAS = {
    "Ouigo": "https://www.ouigo.com/es/",
    "Renfe": "https://www.renfe.com/es/es",
}

#: Lo que delata una campaña de verdad. "Gratis" a secas se quedó fuera a
#: propósito: en estas portadas casi siempre habla del equipaje de cabina, no
#: de un billete.
GANCHOS = re.compile(
    r"(?:\d{1,3}\s*%\s*(?:de\s+)?(?:descuento|dto)|descuento\s+del?\s+\d{1,3}\s*%"
    r"|billetes?\s+desde\s+\d+\s*€|precio\s+único|\bviajes?\s+\w+\s+gratis"
    r"|\buno\s+gratis)",
    re.I,
)

#: Lo que casa con un gancho sin ser una campaña: formularios de suscripción,
#: textos legales, cookies y las ventajas de siempre del equipaje.
RUIDO = re.compile(
    r"newsletter|suscr[ií]b|cookie|pol[ií]tica|condiciones generales|aviso legal"
    r"|equipaje",
    re.I,
)

#: Restos de menú que se cuelan al final de una frase, en mayúsculas y sin
#: puntuación. Se recortan del final para que el aviso no los arrastre.
MENU = re.compile(
    r"(?:\s+(?:MIS RESERVAS|MI CUENTA|INICIA[R]? SESI[ÓO]N|ESPAÑA|Español|Previous button"
    r"|Next button|LOG IN|MENU))+\s*$",
    re.I,
)

LONGITUD_MAXIMA = 220
LONGITUD_MINIMA = 30


@dataclass(frozen=True)
class Promocion:
    compania: str
    texto: str

    @property
    def huella(self) -> str:
        """Identifica la campaña sin depender de espacios ni mayúsculas."""
        plano = unicodedata.normalize("NFD", f"{self.compania}:{self.texto}".lower())
        plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
        return hashlib.sha1(re.sub(r"\s+", " ", plano).encode()).hexdigest()[:12]


def _sin_adornos(texto: str) -> str:
    """Quita los emojis del reclamo publicitario.

    No es cosmética: son decoración que no aporta nada al aviso, y al
    imprimirlos revientan la consola de Windows, que va en cp1252. Se van los
    símbolos (categoría So) y los selectores de variante que los acompañan.
    """
    limpio = "".join(
        c for c in texto
        if unicodedata.category(c) != "So" and not "︀" <= c <= "️"
    )
    return re.sub(r"\s+", " ", limpio).strip()


def _texto_visible(html: str) -> str:
    """Quita scripts, estilos y etiquetas; deja el texto en una sola línea."""
    limpio = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    limpio = re.sub(r"<[^>]+>", " ", limpio)
    # Las portadas traen entidades HTML escapadas dos veces (&#34; y &amp;).
    for entidad, letra in (("&nbsp;", " "), ("&amp;", "&"), ("&#34;", '"'), ("&quot;", '"')):
        limpio = limpio.replace(entidad, letra)
    return re.sub(r"\s+", " ", limpio).strip()


def extraer(compania: str, html: str) -> list[Promocion]:
    """Frases de campaña que aparecen en esa portada, sin repetir.

    Se parte el texto en frases en vez de recortar ventanas de caracteres
    alrededor de cada coincidencia: dos ganchos dentro de la misma frase
    -y las campañas suelen tener varios: "50% de descuento + 10% extra"-
    generaban ventanas solapadas y la misma campaña salía por duplicado.
    """
    frases = re.split(r"(?<=[.!?])\s+|(?:\s*[·|]\s*)", _texto_visible(html))
    encontradas: list[Promocion] = []
    vistas: set[str] = set()

    for frase in frases:
        frase = _sin_adornos(MENU.sub("", frase.strip(" ·|-–—")))
        if not GANCHOS.search(frase) or RUIDO.search(frase):
            continue
        if not LONGITUD_MINIMA <= len(frase):
            continue
        frase = frase[:LONGITUD_MAXIMA].strip()

        clave = re.sub(r"[^a-z0-9]", "", frase.lower())[:60]
        if clave in vistas:
            continue
        vistas.add(clave)
        encontradas.append(Promocion(compania=compania, texto=frase))

    return encontradas


def consultar(user_agent: str, timeout: float = 25.0) -> tuple[list[Promocion], list[str]]:
    """Lee las portadas y devuelve las campañas y los errores que hubo."""
    promociones: list[Promocion] = []
    errores: list[str] = []
    cabeceras = {"User-Agent": user_agent, "Accept-Language": "es-ES,es;q=0.9"}

    with httpx.Client(timeout=timeout, follow_redirects=True, headers=cabeceras) as cliente:
        for compania, url in PORTADAS.items():
            try:
                respuesta = cliente.get(url)
                respuesta.raise_for_status()
            except httpx.HTTPError as error:
                errores.append(f"{compania}: {type(error).__name__}")
                log.warning("promociones: %s no responde (%s)", compania, error)
                continue
            halladas = extraer(compania, respuesta.text)
            log.info("promociones: %d campañas en %s", len(halladas), compania)
            promociones.extend(halladas)

    return promociones, errores


#: Formas en que estas campañas dicen a qué edades van dirigidas. Todas exigen
#: la palabra "años" salvo las que nombran directamente a los menores: sin esa
#: exigencia, "De 4 a 9 personas" se leería como un rango de edad.
RANGOS_EDAD: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"(?:entre|de)\s+(\d{1,2})\s*(?:y|a)\s+(\d{1,2})\s*a[ñn]os", re.I), "rango"),
    (re.compile(r"menores\s+de\s+(\d{1,2})\s*a[ñn]os", re.I), "hasta"),
    (re.compile(r"(?:mayores\s+de|a\s+partir\s+de\s+los)\s+(\d{1,2})\s*a[ñn]os", re.I), "desde"),
    (re.compile(r"\bni[ñn]os?\b|\bmenores\b|\binfantil", re.I), "infantil"),
)

#: Hasta qué edad se considera "niño" cuando la campaña no da un número.
EDAD_INFANTIL = 13


def edades_a_las_que_va(texto: str) -> tuple[int, int] | None:
    """Franja de edad que pide la campaña, o None si no pide ninguna."""
    for patron, forma in RANGOS_EDAD:
        encontrado = patron.search(texto)
        if not encontrado:
            continue
        if forma == "rango":
            desde, hasta = int(encontrado.group(1)), int(encontrado.group(2))
            return (desde, hasta) if desde <= hasta else (hasta, desde)
        if forma == "hasta":
            return 0, int(encontrado.group(1)) - 1
        if forma == "desde":
            return int(encontrado.group(1)), 120
        return 0, EDAD_INFANTIL
    return None


def aplicables(promociones: list[Promocion], edad: int | None) -> list[Promocion]:
    """Descarta las campañas que piden una edad que no se tiene.

    Sin edad configurada no se descarta nada. Y una campaña que no menciona
    ninguna edad se queda siempre: puede ir dirigida a todo el mundo, y es
    preferible enseñar una que no aplica a esconder una que sí.
    """
    if edad is None:
        return list(promociones)

    conservadas = []
    for promocion in promociones:
        franja = edades_a_las_que_va(promocion.texto)
        if franja and not franja[0] <= edad <= franja[1]:
            log.info(
                "promociones: descartada por edad (%d-%d): %s",
                franja[0], franja[1], promocion.texto[:60],
            )
            continue
        conservadas.append(promocion)
    return conservadas


def novedades(
    actuales: list[Promocion], conocidas: list[dict]
) -> tuple[list[Promocion], list[dict]]:
    """Campañas que no estaban antes, y el estado a guardar.

    Devolver también el estado permite que quien llame decida cuándo escribirlo
    (por ejemplo, no escribir nada si la web se cayó y no vino ninguna).
    """
    huellas_previas = {c.get("huella") for c in conocidas}
    nuevas = [p for p in actuales if p.huella not in huellas_previas]

    hoy = date.today().isoformat()
    primera_vez = {c.get("huella"): c.get("desde", hoy) for c in conocidas}
    estado = [
        {
            "huella": p.huella,
            "compania": p.compania,
            "texto": p.texto,
            "desde": primera_vez.get(p.huella, hoy),
        }
        for p in actuales
    ]
    return nuevas, estado


def mensaje(nuevas: list[Promocion]) -> str:
    """Aviso para Telegram. Se manda solo cuando hay algo que no estaba."""
    if not nuevas:
        return ""
    lineas = ["🎉 <b>Campaña nueva en las webs de tren</b>", ""]
    for promocion in nuevas:
        lineas.append(f"<b>{promocion.compania}</b>: {promocion.texto}")
    lineas.append("")
    lineas.append("Ojo: puede pedir edad, grupo o fechas concretas. Comprueba las condiciones.")
    return "\n".join(lineas)
