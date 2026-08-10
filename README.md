# Buscador de trenes Madrid → Elche

**En producción: [viajes-lowcost.vercel.app](https://viajes-lowcost.vercel.app)**

App personal que compara los precios de tren entre Madrid y Elche en varias
webs a la vez, guarda un histórico y avisa por Telegram cuando aparece una
oferta que se sale de lo normal.

No hay servidores ni base de datos: **el repositorio es la infraestructura**.
GitHub Actions ejecuta las búsquedas por cron, comitea los precios en `data/`
y Vercel redespliega la PWA al detectar ese commit.

```
GitHub Actions (cron)
  ├─ buscador Python  →  consulta las fuentes
  ├─ data/historico/*.jsonl   histórico acumulado
  ├─ data/*.json              lo que lee la app
  ├─ Telegram                 avisos de ofertas
  └─ commit  →  Vercel redespliega la PWA
```

## Fuentes

| Fuente | Estado | Cómo funciona |
|---|---|---|
| **Ouigo** | funcionando | API JSON propia. Rápida (~1 s por consulta). |
| **Renfe** (AVE y Avlo) | funcionando | Navegador real con Playwright. Lenta (~30 s por consulta). |
| **iryo** | solo en local | Funciona desde casa, pero Cloudflare le pone un CAPTCHA a las IPs de centro de datos, así que en la nube no trae nada. Apagada en `app.yaml`; ver abajo. |
| **eDreams** | funcionando | Navegador real sobre su URL de resultados. Agrega **AVE, Avlo, Alvia y Ouigo de una vez**, y llega tanto a Elche AV como a Alicante. |
| Trainline | pendiente | Su búsqueda está protegida con DataDome (403 y captcha). Su API de estaciones sí responde sin problema. |
| Omio, trenes.com, promociones | pendiente | Omio carga sin bloqueo, es la siguiente candidata razonable. |

> **Corrección:** al empezar este proyecto se dio por hecho que eDreams no
> vendía trenes. Es falso: `edreams.es/trenes` existe y vende AVE, igual que
> Rumbo, del mismo grupo. Groupon y Oferplan sí siguen siendo cupones de ocio
> y no venden billetes de tren.

### Lo que costó sacar de eDreams

1. **Sí tiene URL de resultados, pero no donde se buscó primero.**
   `/trenes/madrid-elche/` da 404; lo que funciona es
   `…/travel/trains/?step=departure#results/type=O;from=…;to=…;dep=…`, con los
   parámetros en el *hash* y separados por `;`. Cambiar ese hash relanza la
   búsqueda sin recargar. Es la **única fuente de todas que permite enlazar a
   una búsqueda concreta**, así que su enlace sí lleva a la ruta y el día.
2. **Hay que entrar directo a los resultados.** Por la portada aparece un modal
   de login que tapa el formulario y el autocompletado; yendo a la URL de
   resultados no hay formulario que rellenar y el problema no existe.
3. **Publica dos precios y solo uno es real.** Junto al precio normal enseña,
   más grande y en color, una "tarifa Prime" bastante más barata que exige
   suscripción (29,99 €/trimestre tras 15 días de prueba). Es justo el número
   que un extractor descuidado cogería. El adaptador toma siempre el **"Precio
   sin descuento"**, y hay un test que lo vigila.

Su GraphQL (`POST /frontend-api/service/graphql`) no hizo falta: se intentó
interceptar y la petición no pasa por `fetch` ni por `XMLHttpRequest` parcheables
desde fuera. Leer el DOM de los resultados es más simple y no depende de
descubrir el esquema.

### Comprobado: eDreams es más cara que comprar en el operador

No es una sospecha, está medido contra los datos ya recogidos. Mismo tren, mismo
día, mismo horario:

| Comparación | Casos | eDreams frente al operador |
|---|---|---|
| Ouigo | 20 | **+10,85 €** de media (entre +10 y +14) |
| AVE (Atocha → Elche AV, 11/09) | 2 | +11,75 € y +33,50 € |

**En 22 de 22 comparaciones eDreams sale más cara.** Nunca ha empatado.

Entonces, ¿para qué sirve? No para comprar, sino por **cobertura y velocidad**:

- Trae AVE, Avlo, Alvia y Ouigo **en una sola consulta**, y llega a Elche AV y a
  Alicante. Es la única fuente que cubre las dos estaciones y los cuatro
  operadores a la vez.
- 96 ofertas en 145 s, frente a las 164 de Renfe en 578 s. Por oferta es más
  del doble de rápida.
- Sirve de red de seguridad: si Renfe u Ouigo se rompen —y se rompen—, sigue
  habiendo precios de esos operadores.

Sus precios **no estropean la detección de gangas**: la mediana de referencia se
calcula sobre los *mínimos* diarios, y eDreams nunca es la más barata, así que
no entra en el cálculo. Aun así se guardan como fuente aparte y la app enseña
siempre de dónde sale cada precio.

Su "tarifa Prime" (unos 20 € menos por billete) sí bajaría de lo que cobra el
operador, pero exige suscripción: 29,99 €/trimestre, unos 120 € al año. No se
registra en el histórico porque no es un precio que se pueda pagar sin más.

### Lo que costó sacar de iryo

Tres cosas, por si alguna vuelve a romperse:

1. **Necesita Chrome de verdad** (`channel="chrome"`). Con el Chromium que trae
   Playwright devuelve la página en blanco: carga el título y nada más. Por eso
   el workflow instala los dos navegadores.
2. **La fecha hay que picarla en su calendario.** Inyectarla en el
   `input[type=date]` por JS deja el campo correcto, pero Angular no se entera,
   el formulario nunca es válido y BUSCAR se queda deshabilitado. Y sus celdas
   no llevan la fecha en el DOM: hay que cruzar el mes de la cabecera (que va en
   base 0) con el número del día.
3. **Su API no vale.** `api.iryo.eu` existe y responde, pero exige una clave de
   Azure API Management que la web resuelve en tiempo de ejecución y no está en
   su código. Se intentó y es un callejón sin salida.

Y dos limitaciones que no tienen arreglo:

- **iryo no llega a Elche ni a Murcia.** De sus 15 estaciones solo Alicante
  Terminal sirve para esta ruta.
- **Desde la nube no se le puede consultar.** Funcionaba en local y devolvía
  cero en GitHub Actions. `scripts/diagnostico_iryo.py` lo aclaró: Cloudflare
  sirve a esas IPs una pantalla de *"completa este puzzle de seguridad para
  confirmar que no eres un robot"*. No es cosa del navegador —se probaron
  Chrome real, el Chromium de Playwright y Chrome con pantalla vía xvfb, y los
  tres reciben lo mismo—, es la IP. Resolver CAPTCHAs no se contempla, y pagar
  un proxy residencial no tiene sentido para vigilar billetes de 15-30 €.

Por eso está apagada en `config/app.yaml`. Para usarla desde casa:

```bash
python -m buscador buscar --fuentes iryo --guardar
```

Si algún día vuelve a fallar, el adaptador ahora lo dice en una línea en vez de
agotar el tiempo: distingue "la página llega en blanco" de "hay contenido pero
no es el formulario", y en cuanto lo detecta deja de reintentar las demás
consultas, que antes costaban seis minutos y medio para nada.

### Groupon y Oferplan: comprobado que no venden trenes

Se buscó en sus propios buscadores. Groupon devuelve para "tren AVE" un gorro
de punto, un viaje a Amsterdam con vuelos y un enlace de afiliado a códigos de
TrainPal; para "Renfe", clases de defensa personal y una cata de ron. Oferplan
(Las Provincias, grupo Vocento) son cupones de comercios locales y no tiene
transporte. No es que estén bloqueados: es que no tienen el dato.

> **Groupon y Oferplan no venden billetes de tren**, son cupones de ocio local.
> eDreams sí, y está integrada.

Ouigo sale de **Madrid Chamartín** en esta ruta; Renfe también opera desde
**Atocha**. La app consulta ambas y además compara **Elche AV** con **Alicante
Terminal**, marcando los 25 minutos extra de traslado hasta Elche.

## Puesta en marcha

```bash
python -m venv .venv
.venv\Scripts\activate           # en Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium      # solo si vas a usar la fuente Renfe
python -m buscador estaciones    # descubre los códigos de cada web
```

### Avisos por Telegram

1. Habla con [@BotFather](https://t.me/BotFather) → `/newbot` → te da un token.
2. Habla con [@userinfobot](https://t.me/userinfobot) → te dice tu `chat_id`.
3. En GitHub: *Settings → Secrets and variables → Actions* → añade
   `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.

4. Escríbele algo a tu bot desde Telegram. Un bot no puede iniciar la
   conversación, así que hasta que no le hables no te podrá escribir él.

Comprueba que ha quedado bien:

```bash
python -m buscador probar-aviso
```

Para probarlo en local, define esas dos variables de entorno antes de ejecutar.
Si faltan, todo funciona igual pero sin enviar avisos.

## Uso

```bash
# Barrido de calendario (por defecto, 90 días desde mañana)
python -m buscador buscar --fuentes ouigo

# Un rango concreto
python -m buscador buscar --desde 2026-09-01 --hasta 2026-09-30

# Solo un trayecto
python -m buscador buscar --origen madrid_atocha --destino elche_av --fuentes renfe

# Profundizar con todas las fuentes en los días que salieron más baratos
python -m buscador buscar --top-dias 6 --guardar --avisar

# Revisar los viajes fijos de config/vigilancias.yaml
python -m buscador vigilar --guardar --avisar
```

`--guardar` añade lo encontrado al histórico y regenera los JSON de la app.
`--avisar` manda por Telegram las ofertas destacadas que no se hayan avisado ya.

### Por qué existe `--top-dias`

Barrer 90 días con todas las fuentes sería inviable: Renfe tarda medio minuto
por consulta, así que un barrido completo llevaría horas. El reparto es:

1. **Ouigo dibuja el mapa** de precios de todo el horizonte (rápido, por API).
2. **Renfe profundiza** solo en los días que salieron baratos, que son los
   únicos donde de verdad merece la pena comparar operadores.

## Configuración

- **`config/app.yaml`** — estaciones, pasajeros, horizonte, umbrales de oferta,
  ritmo de peticiones y qué fuentes están activas.
  También los **días de ida y de vuelta**, que van por separado a propósito:
  ```yaml
  dias_ida: [viernes]      # Madrid → Elche/Alicante
  dias_vuelta: [lunes]     # Elche/Alicante → Madrid
  ```
  Con una sola lista no habría forma de decir "salgo viernes y vuelvo lunes".
  Deja cualquiera de las dos vacía para buscar todos los días.

  **Estos dos valores deciden qué se busca**, así que son los que ahorran o
  gastan consultas. En la app, dentro de *Ajustes → Días de viaje*, puedes
  filtrar lo que se **muestra** sin tocar el YAML; los días que no se están
  recopilando aparecen en gris, porque marcarlos ahí no hará aparecer precios
  que nunca llegaron a consultarse.
- **`config/vigilancias.yaml`** — viajes con fechas ya decididas que quieres
  vigilar en cada ejecución.
- **`config/estaciones_codigos.yaml`** — generado por `python -m buscador
  estaciones`. No lo edites a mano.

### Qué se considera una oferta destacada

Para cada ruta y fecha de viaje se calcula la **mediana de los precios mínimos
diarios** de los últimos 30 días. Salta el aviso si el precio actual baja un
25 % o más respecto a esa mediana **y** además es el más bajo visto en 14 días.

Mientras no haya al menos 10 días de histórico se usa un umbral absoluto
(25 € por defecto), para que la app sirva desde el primer día. Todo eso se
ajusta en la sección `ofertas` de `config/app.yaml`.

No se repite el mismo aviso dentro de 24 horas (`data/alertas_enviadas.json`).

## La app del móvil

```bash
npm --prefix web install
node scripts/preparar-datos.mjs   # copia data/*.json dentro de la web
npm --prefix web run dev
```

En producción está en **Vercel**. Ábrela en Chrome desde el móvil y usa
*Añadir a pantalla de inicio*: se instala como app y funciona sin cobertura
mostrando los últimos datos descargados.

El despliegue lo define `vercel.json` en la raíz: compila `web/` después de
copiar los precios, y publica `web/dist`.

Cuatro pestañas en una barra inferior, pensada para el pulgar:

- **Ofertas** — lo que ha bajado de forma llamativa.
- **Calendario** — precio más bajo por día, ida y vuelta por separado.
- **Trenes** — todo, ordenado por precio y filtrable.
- **Ajustes** — tu horario preferido, el índice de compañías y el estado de
  cada web.

**El color identifica siempre a la compañía**, y es el único acento cromático
fuerte de la interfaz: AVE morado, Avlo magenta, Ouigo azul, iryo rojo. Cada
tarjeta lleva el borde de quien vende ese billete.

### Por qué los botones llevan a la portada del operador

Ninguna web de tren permite enlazar a un billete ni a una búsqueda concreta.
Comprobado uno por uno:

| Web | Qué pasa |
|---|---|
| **Renfe** | Genera los resultados por POST y los identifica con un token de sesión (`buscarTrenEnlaces.do?c=_XXXX`). Caduca y solo vale en el navegador que hizo la búsqueda. |
| **Ouigo** | Ignora los parámetros de la URL: entres como entres, acabas en su portada. |
| **Trainline** | Sí acepta trayecto y fecha, pero protege esa página con DataDome y salta un captcha con frecuencia. Un enlace que a veces lleva a un captcha es peor que no tener enlace. |

Por eso cada tarjeta tiene dos botones: **Copiar datos**, que deja el trayecto,
la fecha y la hora en el portapapeles, y **Abrir Renfe / Abrir Ouigo**, que va
a su buscador. Rellenarlo son diez segundos y el enlace nunca se rompe.

### Filtros y horario preferido

Se guardan en el propio móvil (`localStorage`), no en el repositorio: son tuyos,
cambian a menudo y quieres tocarlos desde el teléfono sin esperar a un
despliegue. Puedes filtrar por sentido, compañía y franja horaria
(madrugada / mañana / tarde / noche), y ocultar los trenes a Alicante que
obligan a un traslado.

## Automatización

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `vigilar-rapido.yml` | **cada hora** | Vigilancias + 8 días más baratos, solo con Ouigo (API). |
| `vigilar-completo.yml` | **cada 6 h** | Lo mismo pero con todas las fuentes, incluida Renfe. |
| `calendario.yml` | diario, 06:30 | Barrido de los 90 días con Ouigo. |
| `tests.yml` | al cambiar el código | Ejecuta los tests. |

Los tres primeros comparten el grupo de concurrencia `datos` para no pisarse al
comitear. El despliegue no necesita workflow: Vercel está conectado al
repositorio y redespliega solo cuando cambian los datos.

### Por qué dos cadencias distintas

No tiene sentido que todas las fuentes vayan al mismo ritmo:

- **Ouigo cuesta ~1 s por consulta** (API JSON). Mirar cada hora es barato para
  ellos y para nosotros, y te pilla las bajadas casi al momento.
- **Renfe cuesta ~30 s por consulta** porque hay que abrir un navegador de
  verdad. Consultarla cada hora sería machacar su web para nada: las tarifas no
  cambian tan rápido.

Si algún día quieres cambiarlo, es el `cron` de cada workflow.

El histórico **solo anota los cambios**: si un tren sigue costando lo mismo
que la última vez, no se escribe otra línea. Con la vigilancia horaria eso es
la diferencia entre unos megabytes al mes y unos pocos kilobytes, y la mediana
sale igual porque le basta un punto por día.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

Cubren la lógica que no depende de ninguna web: cálculo de medianas, criterios
de detección de ofertas, filtrado de días de la semana y deduplicación del
mismo tren visto en varias fuentes. Son rápidos y no se rompen porque Renfe
cambie su HTML.

## ¿Son reales los precios?

Sí, y está comprobado, no supuesto. Los precios salen de donde se venden: la
API de venta de Ouigo (la misma que usa su web) y la página de resultados real
de Renfe. Contrastando lo publicado contra las webs en vivo, **35 de 35 trenes
coincidían al céntimo** (9 de Ouigo, 26 de Renfe).

Tres advertencias honestas:

- **Caducan.** Las tarifas son dinámicas. Por eso cada pantalla dice cuándo se
  actualizó: un precio de hace tres horas puede haberse movido.
- **Es el más barato del tren.** Renfe muestra "precio desde", que es la tarifa
  Básica. Elige o Prémium cuestan más.
- **Un adulto sin descuentos.** Con Tarjeta Joven o Dorada pagarás menos de lo
  que dice la app.

### Control de credibilidad

Raspar una web es leer números de un HTML que puede cambiar sin avisar. Un
fallo total se detecta solo (la fuente devuelve cero), pero uno sutil —el
extractor empieza a coger la celda de al lado— acabaría en tu móvil como si
fuera un precio bueno.

Por eso cada dato pasa un control antes de publicarse: precio entre 5 y 600 €,
duración entre 30 minutos y 10 horas, y fecha y trayecto iguales a los que se
pidieron. Lo que no pasa se descarta, y si en una ejecución se descarta más de
lo que se acepta, la fuente se marca en rojo en la pestaña de Ajustes: eso ya
no es un dato raro suelto, es el lector roto.

## Mantenimiento

Esto es raspado web y las webs cambian. Cada fuente está aislada en su propio
fichero (`buscador/adaptadores/`), así que cuando una se rompa:

- La ejecución **no se cae**: las demás fuentes siguen y el fallo se registra
  en `data/estado_fuentes.json`, visible en la pestaña *Fuentes* de la app.
- Solo hay que retocar el adaptador afectado. El de Renfe documenta en su
  cabecera el orden exacto de pasos, que es lo que más cuesta reconstruir.

## Estructura

```
buscador/            paquete Python
  adaptadores/       una fuente por fichero (ouigo.py, renfe.py, base.py)
  modelos.py         Oferta, Consulta, Estacion
  consultas.py       planes de búsqueda (calendario, top-días, vigilancias)
  historico.py       JSONL y medianas
  ofertas.py         detección de gangas y antispam
  exportar.py        genera los JSON de la PWA
  avisos/telegram.py
config/              tu configuración
data/                histórico y JSON publicados
scripts/             utilidades del build
tests/               pruebas de la lógica interna
web/src/             PWA (Vite + React + TypeScript)
  App.tsx            las cuatro vistas
  componentes.tsx    tarjeta de tren, chips, iconos, estados vacíos
  companias.ts       color e identidad de cada operador
  preferencias.ts    filtros del usuario en localStorage
  datos.ts           carga de los JSON y formateo
  estilos.css        el sistema visual entero
```
