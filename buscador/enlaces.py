"""Enlaces de compra.

**Ninguna de estas webs permite enlazar a un billete ni a una búsqueda
concreta.** Está comprobado, uno por uno:

- **Renfe** genera la página de resultados por POST y la identifica con un
  token de sesión (``buscarTrenEnlaces.do?c=_XXXX``). Ese token caduca y solo
  vale en el navegador que hizo la búsqueda: pegado en otro sitio no lleva a
  ninguna parte. Su formulario por GET redirige a una página vacía.
- **Ouigo** ignora los parámetros de la URL. Le pongas lo que le pongas,
  aterrizas en su portada.
- **Trainline** sí acepta trayecto y fecha en la URL, pero protege esa página
  con DataDome: al abrirla salta un captcha con bastante frecuencia. Un enlace
  que a veces lleva a un captcha es peor que no tener enlace.

Así que el enlace va a la portada del operador —que siempre funciona— y la
app ofrece copiar los datos del viaje para rellenar su buscador en segundos.
Es menos cómodo, pero es honesto: nada de prometer un billete que el enlace
no puede abrir.
"""

from __future__ import annotations

#: Dónde comprar a cada operador. Es su portada: no hay forma de apuntar más
#: fino, ver la explicación de arriba.
OPERADORES: dict[str, str] = {
    "ouigo": "https://www.ouigo.com/es/",
    "renfe": "https://www.renfe.com/es/es",
    "ave": "https://www.renfe.com/es/es",
    "avlo": "https://www.renfe.com/es/es",
    "iryo": "https://iryo.eu/es/home",
}

POR_DEFECTO = "https://www.renfe.com/es/es"


def web_operador(operador: str) -> str:
    """Portada del operador que vende ese billete."""
    return OPERADORES.get((operador or "").lower(), POR_DEFECTO)
