"""Interfaz de línea de comandos del buscador.

Comandos:
    buscar      barrido de calendario entre dos fechas
    vigilar     revisa los viajes fijos de config/vigilancias.yaml
    estaciones  descubre y guarda los códigos de estación de cada fuente
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta

from . import adaptadores as _adaptadores  # noqa: F401 - registra los adaptadores
from . import historico, ofertas as motor_ofertas
from .adaptadores import base
from .avisos import enviar_gangas
from .config import Config, cargar_config
from .consultas import plan_calendario, plan_top_dias, plan_vigilancias
from .exportar import exportar_todo
from .modelos import Consulta, Oferta, ResultadoFuente
from .salida import consola, mejores_por_tren, tabla_fuentes, tabla_ofertas


def _fecha(texto: str) -> date:
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Fecha inválida: {texto!r}. Usa el formato AAAA-MM-DD."
        ) from error


def _filtrar_estaciones(config: Config, ids: list[str] | None, cuales: str):
    disponibles = getattr(config.estaciones, cuales)
    if not ids:
        return disponibles
    seleccionadas = [config.estaciones.por_id(id_estacion) for id_estacion in ids]
    return seleccionadas


def _lanzar(config: Config, consultas: list[Consulta], solo: list[str] | None):
    """Ejecuta todos los adaptadores activos sobre el plan de consultas."""
    instancias = base.crear_adaptadores(config)
    if solo:
        instancias = [a for a in instancias if a.nombre in solo]

    if not instancias:
        consola.print(
            "[red]No hay ninguna fuente activa.[/red] Revisa la sección [bold]fuentes[/bold] "
            "de config/app.yaml y que el adaptador esté implementado."
        )
        return [], []

    consola.print(
        f"Consultando [bold]{len(instancias)}[/bold] fuentes "
        f"× [bold]{len(consultas)}[/bold] trayectos…"
    )

    ofertas: list[Oferta] = []
    resultados: list[ResultadoFuente] = []
    for adaptador in instancias:
        encontradas, resultado = base.ejecutar(adaptador, consultas)
        ofertas.extend(encontradas)
        resultados.append(resultado)
        if hasattr(adaptador, "cerrar"):
            adaptador.cerrar()

    return ofertas, resultados


def _cerrar_ciclo(
    config: Config,
    encontradas: list[Oferta],
    resultados: list[ResultadoFuente],
    args: argparse.Namespace,
) -> list:
    """Guarda el histórico, detecta gangas, avisa y exporta para la PWA.

    Importante: la referencia histórica se calcula ANTES de guardar lo recién
    capturado. Si no, la oferta de hoy entraría en su propia mediana y una
    bajada fuerte se disimularía a sí misma.
    """
    if not args.guardar and not args.avisar:
        return []

    referencia = historico.Referencia(historico.cargar())
    gangas = motor_ofertas.detectar(encontradas, referencia, config)

    if args.guardar:
        guardadas = historico.guardar(encontradas)
        consola.print(f"Histórico: {guardadas} registros añadidos.")

    if gangas:
        consola.print(f"\n[bold green]{len(gangas)} ofertas destacadas[/bold green]")
        for ganga in gangas:
            consola.print(f"  • {ganga.oferta.resumen()} — {ganga.motivo}")

    if args.avisar:
        nuevas = motor_ofertas.filtrar_repetidas(gangas, config.ofertas.antispam_horas)
        enviados = enviar_gangas(nuevas)
        if enviados:
            motor_ofertas.registrar_enviadas(nuevas, config.ofertas.antispam_horas)
            consola.print(f"Telegram: {enviados} avisos enviados.")
        elif nuevas:
            consola.print("[yellow]Telegram sin configurar: avisos no enviados.[/yellow]")

    if args.guardar:
        exportar_todo(encontradas, resultados, gangas, config)
        consola.print("Datos exportados a data/ para la PWA.")

    return gangas


def cmd_buscar(args: argparse.Namespace) -> int:
    config = cargar_config()

    if args.top_dias:
        consultas = plan_top_dias(config, args.top_dias)
        consola.print(
            f"Profundizando en los [bold]{args.top_dias}[/bold] días más baratos "
            f"de cada ruta según data/calendario.json."
        )
    else:
        desde = args.desde or date.today() + timedelta(days=1)
        hasta = args.hasta or desde + timedelta(days=config.busqueda.horizonte_dias)
        consultas = plan_calendario(
            config,
            desde,
            hasta,
            origenes=_filtrar_estaciones(config, args.origen, "origen"),
            destinos=_filtrar_estaciones(config, args.destino, "destino"),
        )

    ofertas, resultados = _lanzar(config, consultas, args.fuentes)
    tabla_ofertas(mejores_por_tren(ofertas)[: args.limite], "Mejores precios encontrados")
    tabla_fuentes(resultados)
    _cerrar_ciclo(config, ofertas, resultados, args)
    return 0 if ofertas else 1


def cmd_vigilar(args: argparse.Namespace) -> int:
    config = cargar_config()
    consultas = plan_vigilancias(config)

    if not consultas:
        consola.print(
            "[yellow]No hay vigilancias definidas.[/yellow] "
            "Añade viajes a config/vigilancias.yaml."
        )
        return 0

    ofertas, resultados = _lanzar(config, consultas, args.fuentes)
    tabla_ofertas(mejores_por_tren(ofertas), "Vigilancias")
    tabla_fuentes(resultados)
    _cerrar_ciclo(config, ofertas, resultados, args)
    return 0


def cmd_estaciones(args: argparse.Namespace) -> int:
    from .config import guardar_codigos

    config = cargar_config()
    instancias = base.crear_adaptadores(config)
    if args.fuentes:
        instancias = [a for a in instancias if a.nombre in args.fuentes]

    todas = config.estaciones.todas()
    descubiertos: dict[str, dict[str, str]] = {}

    for adaptador in instancias:
        try:
            codigos = adaptador.descubrir_estaciones(todas)
        except Exception as error:  # noqa: BLE001
            consola.print(f"[red]{adaptador.nombre}: {error}[/red]")
            continue
        finally:
            if hasattr(adaptador, "cerrar"):
                adaptador.cerrar()

        for id_estacion, codigo in codigos.items():
            descubiertos.setdefault(id_estacion, {})[adaptador.nombre] = codigo
            consola.print(f"  {adaptador.nombre}: {id_estacion} → [bold]{codigo}[/bold]")

    if not descubiertos:
        consola.print("[yellow]Ninguna fuente ha devuelto códigos de estación.[/yellow]")
        return 1

    guardar_codigos(descubiertos)
    consola.print("[green]Códigos guardados en config/estaciones_codigos.yaml[/green]")
    return 0


def _opciones_ciclo(parser: argparse.ArgumentParser) -> None:
    """Opciones comunes a buscar y vigilar (las que usa el cron)."""
    parser.add_argument(
        "--guardar", action="store_true",
        help="Añade lo encontrado al histórico y regenera los JSON de la PWA.",
    )
    parser.add_argument(
        "--avisar", action="store_true",
        help="Envía por Telegram las ofertas destacadas que no se hayan avisado ya.",
    )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="buscador",
        description="Busca los billetes de tren más baratos de Madrid a Elche.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Traza detallada.")

    subs = parser.add_subparsers(dest="comando", required=True)

    p_buscar = subs.add_parser("buscar", help="Barrido de calendario entre dos fechas.")
    p_buscar.add_argument("--desde", type=_fecha, help="Fecha inicial (AAAA-MM-DD).")
    p_buscar.add_argument("--hasta", type=_fecha, help="Fecha final (AAAA-MM-DD).")
    p_buscar.add_argument("--origen", nargs="*", help="Ids de estación de origen.")
    p_buscar.add_argument("--destino", nargs="*", help="Ids de estación de destino.")
    p_buscar.add_argument("--fuentes", nargs="*", help="Limitar a estas fuentes.")
    p_buscar.add_argument("--limite", type=int, default=40, help="Filas a mostrar.")
    p_buscar.add_argument(
        "--top-dias", type=int, metavar="N",
        help="En vez de barrer un rango, consulta solo los N días más baratos "
             "de cada ruta según data/calendario.json. Pensado para las fuentes "
             "lentas, después de un barrido con una fuente rápida.",
    )
    _opciones_ciclo(p_buscar)
    p_buscar.set_defaults(func=cmd_buscar)

    p_vigilar = subs.add_parser("vigilar", help="Revisa config/vigilancias.yaml.")
    p_vigilar.add_argument("--fuentes", nargs="*", help="Limitar a estas fuentes.")
    _opciones_ciclo(p_vigilar)
    p_vigilar.set_defaults(func=cmd_vigilar)

    p_est = subs.add_parser("estaciones", help="Descubre los códigos de estación.")
    p_est.add_argument("--fuentes", nargs="*", help="Limitar a estas fuentes.")
    p_est.set_defaults(func=cmd_estaciones)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except (FileNotFoundError, KeyError, ValueError) as error:
        consola.print(f"[red]Error:[/red] {error}")
        return 2
    except KeyboardInterrupt:
        consola.print("\n[yellow]Interrumpido.[/yellow]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
