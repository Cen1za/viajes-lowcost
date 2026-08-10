# Buscador de trenes Madrid → Elche

App personal que compara los precios de tren entre Madrid y Elche en varias
webs a la vez, guarda un histórico y avisa por Telegram cuando aparece una
oferta que se sale de lo normal.

No hay servidores ni base de datos: **el repositorio es la infraestructura**.
GitHub Actions ejecuta las búsquedas por cron, comitea los precios en `data/`
y GitHub Pages sirve una PWA que lee esos ficheros.

```
GitHub Actions (cron)
  ├─ buscador Python  →  consulta las fuentes
  ├─ data/historico/*.jsonl   histórico acumulado
  ├─ data/*.json              lo que lee la app
  ├─ Telegram                 avisos de ofertas
  └─ commit → GitHub Pages    publica la PWA
```

## Fuentes

| Fuente | Estado | Cómo funciona |
|---|---|---|
| **Ouigo** | funcionando | API JSON propia. Rápida (~1 s por consulta). |
| **Renfe** (AVE y Avlo) | funcionando | Navegador real con Playwright. Lenta (~30 s por consulta). |
| iryo | pendiente | Ver el diagnóstico más abajo. |
| Trainline | pendiente | Su búsqueda está protegida con DataDome (403). Su API de estaciones sí responde sin problema. |
| Omio, trenes.com, promociones | pendiente | — |

### Diagnóstico de iryo (para quien lo retome)

Está a medio camino y esto es lo que ya se sabe, para no repetir el trabajo:

- Su web **sí carga** con navegador real; solo bloquea las peticiones directas
  (Cloudflare responde 403 idéntico a cualquier ruta, incluso inexistente).
- `https://iryo.eu/assets/properties/config.json` publica toda su arquitectura.
  Los endpoints que interesan son `api.iryo.eu/b2c/availability` (búsqueda) y
  `api.iryo.eu/b2c/support/stations` (estaciones).
- Esas rutas **existen**: llamadas desde dentro de la página responden 401 con
  *"missing subscription key"*, no 404. Es Azure API Management.
- La clave **no está en el bundle**. El código la asigna desde `this.apiManager`,
  o sea que se resuelve en tiempo de ejecución (probablemente vía
  `api.iryo.eu/b2c/config` o el flujo de Keycloak que también carga la web).

El siguiente paso lógico es interceptar una búsqueda real con
`page.on("request")` y leer la cabecera `Ocp-Apim-Subscription-Key` que envía
la propia SPA. La dificultad añadida es que su buscador va en web components
con shadow DOM, así que hay que usar los locators de Playwright (que sí lo
atraviesan) en vez de `querySelector`.

> **eDreams, Groupon y Oferplan no venden billetes de AVE.** eDreams es vuelos y
> hoteles; los otros dos son cupones de ocio local. Por eso no aparecen aquí.

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
cd web
npm install
mkdir -p public/data && cp ../data/*.json public/data/
npm run dev
```

En producción se publica sola en GitHub Pages. Ábrela en Chrome desde el móvil
y usa *Añadir a pantalla de inicio*: se instala como app y funciona sin
cobertura mostrando los últimos datos descargados.

Cuatro vistas: **Ofertas** destacadas, **Calendario** con mapa de calor de
precios, **Trenes** ordenados por precio y **Fuentes** con el estado de cada web.

## Automatización

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `calendario.yml` | diario, 06:30 | Barrido del horizonte completo con Ouigo. |
| `vigilar.yml` | cada 4 h | Vigilancias + los 6 días más baratos, con todas las fuentes. |
| `desplegar.yml` | al cambiar `web/` o `data/` | Compila y publica la PWA. |
| `tests.yml` | al cambiar el código | Ejecuta los tests. |

Los dos primeros comparten el grupo de concurrencia `datos` para no pisarse al
comitear.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

Cubren la lógica que no depende de ninguna web: cálculo de medianas, criterios
de detección de ofertas, filtrado de días de la semana y deduplicación del
mismo tren visto en varias fuentes. Son rápidos y no se rompen porque Renfe
cambie su HTML.

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
web/                 PWA (Vite + React + TypeScript)
```
