"""Genera los iconos de la PWA a partir del mismo dibujo que el favicon.

Hace falta PNG y no vale solo el SVG: Chrome exige 192 y 512 en PNG para
ofrecer instalar la app, y Safari no acepta SVG en `apple-touch-icon`, así que
en el iPhone el icono saldría en blanco.

Se ejecuta a mano cuando cambia el dibujo o el color, y los PNG se guardan en
el repositorio. Así el despliegue no necesita Python ni Pillow para nada:

    python scripts/generar_iconos.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parent.parent / "web" / "public"

#: El rosa de la app (--marca en web/src/estilos.css).
MARCA = "#b3126b"
BLANCO = "#ffffff"

#: Se dibuja a 4× y se reduce: Pillow no antialiasa las formas, pero reducir
#: con LANCZOS deja los bordes igual de limpios y sale más barato que rasterizar.
SUPER = 4

#: El dibujo original está pensado sobre un lienzo de 64×64.
LIENZO = 64


def _dibujar(tamano: int, margen: float, esquinas: bool) -> Image.Image:
    """Un icono cuadrado con el tren.

    `margen` es la parte del lienzo que se deja libre alrededor del dibujo: los
    iconos *maskable* de Android se recortan en círculo, así que su contenido
    tiene que caber en el 80% central o pierde las esquinas.
    """
    lado = tamano * SUPER
    imagen = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    lapiz = ImageDraw.Draw(imagen)

    # Fondo: con esquinas redondeadas si el icono se muestra tal cual, y a
    # sangre cuando lo va a recortar el sistema.
    if esquinas:
        lapiz.rounded_rectangle((0, 0, lado - 1, lado - 1), radius=lado * 14 / LIENZO,
                                fill=MARCA)
    else:
        lapiz.rectangle((0, 0, lado - 1, lado - 1), fill=MARCA)

    # Escala y desplazamiento del dibujo dentro del lienzo.
    escala = lado * (1 - 2 * margen) / LIENZO
    desplazo = lado * margen

    def p(x: float, y: float) -> tuple[float, float]:
        return (desplazo + x * escala, desplazo + y * escala)

    def caja(x1: float, y1: float, x2: float, y2: float) -> tuple[float, ...]:
        return (*p(x1, y1), *p(x2, y2))

    # Cuerpo del tren.
    lapiz.rounded_rectangle(caja(14, 12, 50, 46), radius=8 * escala, fill=BLANCO)
    # Ventanilla.
    lapiz.rounded_rectangle(caja(19, 18, 45, 30), radius=3 * escala, fill=MARCA)
    # Faros.
    for cx in (24, 40):
        lapiz.ellipse(caja(cx - 3.5, 38 - 3.5, cx + 3.5, 38 + 3.5), fill=MARCA)
    # Las dos patas de la vía.
    for x1, y1, x2, y2 in ((20, 50, 15, 56), (44, 50, 49, 56)):
        lapiz.line((*p(x1, y1), *p(x2, y2)), fill=BLANCO,
                   width=int(4.5 * escala), joint="curve")
        for x, y in ((x1, y1), (x2, y2)):
            r = 2.25 * escala  # remate redondo, que Pillow no hace en line()
            lapiz.ellipse((p(x, y)[0] - r, p(x, y)[1] - r,
                           p(x, y)[0] + r, p(x, y)[1] + r), fill=BLANCO)

    return imagen.resize((tamano, tamano), Image.LANCZOS)


def main() -> None:
    iconos = {
        # Los dos tamaños que pide Chrome para ofrecer la instalación.
        "icono-192.png": _dibujar(192, margen=0.0, esquinas=True),
        "icono-512.png": _dibujar(512, margen=0.0, esquinas=True),
        # Maskable: fondo a sangre y dibujo encogido dentro de la zona segura.
        "icono-maskable-512.png": _dibujar(512, margen=0.18, esquinas=False),
    }
    for nombre, imagen in iconos.items():
        ruta = DESTINO / nombre
        imagen.save(ruta, "PNG", optimize=True)
        print(f"{ruta.relative_to(DESTINO.parent.parent)}  {imagen.size[0]}px")


if __name__ == "__main__":
    main()
