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
