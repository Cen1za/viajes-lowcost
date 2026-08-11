"""Presentación por consola de ofertas y estado de las fuentes."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table

from .modelos import Oferta, ResultadoFuente

# La consola de Windows va en cp1252 y revienta con cualquier carácter que no
# quepa ahí: una flecha "→", un emoji, y a veces hasta los acentos. No es un
# detalle estético, es un UnicodeEncodeError que tumba el comando entero
# después de haber hecho el trabajo. Se pide UTF-8 y, si el terminal no puede,
# que sustituya el carácter en vez de fallar.
for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # ya reconfigurado, o no es un fichero real
        pass

consola = Console()


def tabla_ofertas(ofertas: list[Oferta], titulo: str = "Mejores precios") -> None:
    if not ofertas:
        consola.print("[yellow]No se ha encontrado ninguna oferta.[/yellow]")
        return

    tabla = Table(title=titulo, header_style="bold cyan")
    tabla.add_column("Fecha", no_wrap=True)
    tabla.add_column("Desde", no_wrap=True)
    tabla.add_column("Hasta", no_wrap=True)
    tabla.add_column("Operador", no_wrap=True)
    tabla.add_column("Salida", justify="right", no_wrap=True)
    tabla.add_column("Llegada", justify="right", no_wrap=True)
    tabla.add_column("Dur.", justify="right", no_wrap=True)
    tabla.add_column("Precio", justify="right", no_wrap=True)
    tabla.add_column("Fuente", no_wrap=True)

    ordenadas = sorted(ofertas, key=lambda o: (o.precio_eur, o.fecha_salida, o.hora_salida))
    precio_minimo = ordenadas[0].precio_eur

    for oferta in ordenadas:
        precio = f"{oferta.precio_eur:.2f} €"
        estilo = "bold green" if oferta.precio_eur == precio_minimo else ""
        horas, minutos = divmod(oferta.duracion_min, 60)
        tabla.add_row(
            f"{oferta.fecha_salida:%d/%m}",
            oferta.origen_nombre,
            oferta.destino_nombre,
            oferta.operador,
            f"{oferta.hora_salida:%H:%M}",
            f"{oferta.hora_llegada:%H:%M}",
            f"{horas}h{minutos:02d}",
            precio,
            oferta.fuente,
            style=estilo,
        )

    consola.print(tabla)


def tabla_fuentes(resultados: list[ResultadoFuente]) -> None:
    if not resultados:
        return

    tabla = Table(title="Estado de las fuentes", header_style="bold cyan")
    tabla.add_column("Fuente")
    tabla.add_column("Estado")
    tabla.add_column("Ofertas", justify="right")
    tabla.add_column("Tiempo", justify="right")
    tabla.add_column("Incidencia")

    for resultado in resultados:
        estado = "[green]OK[/green]" if resultado.ok else "[red]FALLO[/red]"
        tabla.add_row(
            resultado.fuente,
            estado,
            str(resultado.ofertas),
            f"{resultado.duracion_s:.1f}s",
            (resultado.error or "")[:80],
        )

    consola.print(tabla)


def mejores_por_tren(ofertas: list[Oferta]) -> list[Oferta]:
    """Colapsa el mismo tren visto en varias fuentes, quedándose con el más barato."""
    mejores: dict[str, Oferta] = {}
    for oferta in ofertas:
        actual = mejores.get(oferta.clave_tren)
        if actual is None or oferta.precio_eur < actual.precio_eur:
            mejores[oferta.clave_tren] = oferta
    return list(mejores.values())
