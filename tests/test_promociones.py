"""Pruebas del vigilante de campañas de Renfe y Ouigo.

Lo que se protege aquí es que **no se convierta en ruido**. Un aviso diario
repitiendo las mismas cuatro promociones acaba en que no se lee ninguno, así
que solo puede hablar cuando aparece algo que antes no estaba. Y como estas
portadas mezclan campañas con menús, cookies y las ventajas de siempre del
equipaje, también se comprueba qué se descarta.
"""

from buscador.promociones import Promocion, extraer, mensaje, novedades

#: Trozo de portada con lo bueno y lo malo mezclado, como viene de verdad.
PORTADA = """
<html><head><style>.x{color:red}</style></head><body>
<script>var promo = "70% de descuento falso dentro de un script";</script>
<div class="banner">Si tienes entre 18 y 30 anios, viaja con un 50% de descuento
+ 10% extra OUIGO. MIS RESERVAS MI CUENTA</div>
<p>Lleva gratis tu equipaje de cabina junto con un equipaje de mano.</p>
<p>De 4 a 9 personas, todo son ventajas: compartis el viaje y un 8% de descuento.</p>
<p>Suscribete a nuestra newsletter y recibe un 5% de descuento en tu proxima compra.</p>
<p>Billetes desde 9 &euro; en tus destinos favoritos.</p>
<p>Corto: 20% dto.</p>
</body></html>
"""


def test_encuentra_las_campanas_reales():
    textos = [p.texto for p in extraer("Ouigo", PORTADA)]
    assert any("50% de descuento" in t for t in textos)
    assert any("8% de descuento" in t for t in textos)


def test_ignora_lo_que_no_es_campana():
    textos = " | ".join(p.texto for p in extraer("Ouigo", PORTADA))
    assert "script" not in textos, "lo de dentro de <script> no cuenta"
    assert "equipaje" not in textos, "el equipaje gratis no es una campaña"
    assert "newsletter" not in textos, "el gancho de suscripción tampoco"
    assert "20% dto" not in textos, "demasiado corto para decir nada"


def test_no_repite_la_misma_campana():
    """Una campaña con varios ganchos ('50% + 10% extra') salía duplicada."""
    textos = [p.texto for p in extraer("Ouigo", PORTADA)]
    assert len(textos) == len(set(textos))
    assert sum(1 for t in textos if "18 y 30" in t) == 1


def test_limpia_los_restos_de_menu():
    banner = next(p.texto for p in extraer("Ouigo", PORTADA) if "18 y 30" in p.texto)
    assert "MIS RESERVAS" not in banner and "MI CUENTA" not in banner


def test_los_emojis_no_llegan_al_texto():
    """Reventaban la consola de Windows y no aportan nada al aviso."""
    html = "<p>Verano joven ☀️ con un 50% de descuento para todos.</p>"
    assert "☀" not in extraer("Ouigo", html)[0].texto


def test_solo_es_novedad_lo_que_no_estaba():
    vieja = Promocion("Renfe", "De 4 a 9 personas y un 8% de descuento.")
    nueva = Promocion("Ouigo", "Billetes desde 9 euros con un 40% de descuento.")

    nuevas, estado = novedades([vieja, nueva], [{"huella": vieja.huella, "desde": "2026-01-01"}])

    assert [p.texto for p in nuevas] == [nueva.texto]
    assert len(estado) == 2


def test_conserva_desde_cuando_se_vio_cada_campana():
    """Que siga anunciada no la convierte en nueva ni le cambia la fecha."""
    promocion = Promocion("Renfe", "Viaja con un 30% de descuento este verano.")
    conocidas = [{"huella": promocion.huella, "desde": "2026-03-04"}]

    nuevas, estado = novedades([promocion], conocidas)

    assert nuevas == []
    assert estado[0]["desde"] == "2026-03-04"


def test_la_huella_ignora_mayusculas_y_espacios():
    """Un retoque de maquetación no puede hacerla pasar por campaña nueva."""
    a = Promocion("Renfe", "Viaja con un 30% de   descuento")
    b = Promocion("Renfe", "VIAJA CON UN 30% DE DESCUENTO")
    assert a.huella == b.huella


def test_sin_novedades_no_hay_mensaje():
    assert mensaje([]) == ""


def test_el_mensaje_avisa_de_las_condiciones():
    texto = mensaje([Promocion("Ouigo", "50% de descuento para jóvenes.")])
    assert "Ouigo" in texto and "50%" in texto
    assert "condiciones" in texto.lower()


# -- Filtro por edad --------------------------------------------------------
#
# Con 45 años, las campañas de "18 a 30" no sirven de nada y solo hacen ruido.
# Lo delicado es no pasarse: una campaña sin edad puede ser para todo el mundo.

from buscador.promociones import aplicables, edades_a_las_que_va  # noqa: E402

JOVEN = Promocion("Ouigo", "Si tienes entre 18 y 30 años, viaja con un 50% de descuento.")
GRUPO = Promocion("Renfe", "De 4 a 9 personas, todo son ventajas: un 8% de descuento.")
TODOS = Promocion("Renfe", "Cada dos viajes, uno gratis por ser Más Renfe.")
NINOS = Promocion("Renfe", "Bajamos el billete para niños a 5 € con un 50% de descuento.")


def test_lee_el_rango_de_edad():
    assert edades_a_las_que_va(JOVEN.texto) == (18, 30)
    assert edades_a_las_que_va("Para menores de 14 años, 40% de descuento") == (0, 13)
    assert edades_a_las_que_va("Mayores de 60 años, 30% de descuento") == (60, 120)


def test_de_4_a_9_personas_no_es_una_edad():
    """El fallo evidente: leer 'de 4 a 9 personas' como si fueran años."""
    assert edades_a_las_que_va(GRUPO.texto) is None


def test_a_los_45_se_van_las_de_jovenes_y_ninos():
    quedan = aplicables([JOVEN, GRUPO, TODOS, NINOS], 45)
    assert quedan == [GRUPO, TODOS]


def test_a_los_25_si_sirve_la_de_jovenes():
    assert JOVEN in aplicables([JOVEN, TODOS], 25)


def test_sin_edad_configurada_no_se_descarta_nada():
    assert aplicables([JOVEN, GRUPO, TODOS, NINOS], None) == [JOVEN, GRUPO, TODOS, NINOS]


def test_una_campana_sin_edad_siempre_se_queda():
    """Mejor enseñar una que no aplica que esconder una que sí."""
    assert aplicables([TODOS], 45) == [TODOS] and aplicables([TODOS], 20) == [TODOS]
