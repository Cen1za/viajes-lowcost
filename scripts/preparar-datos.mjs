/**
 * Copia los precios de data/ dentro de la web antes de compilarla.
 *
 * La fuente de verdad son los JSON de data/ que comitea GitHub Actions. La PWA
 * los lee como ./data/*.json, así que tienen que viajar dentro del bundle.
 * En Node puro para que funcione igual en Windows y en los runners de Vercel.
 */

import { copyFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const raiz = join(dirname(fileURLToPath(import.meta.url)), '..')
const origen = join(raiz, 'data')
const destino = join(raiz, 'web', 'public', 'data')

mkdirSync(destino, { recursive: true })

if (!existsSync(origen)) {
  console.warn('Aún no hay carpeta data/: la web se compilará sin precios.')
  process.exit(0)
}

const ficheros = readdirSync(origen).filter((f) => f.endsWith('.json'))

for (const fichero of ficheros) {
  copyFileSync(join(origen, fichero), join(destino, fichero))
}

console.log(
  ficheros.length
    ? `Copiados ${ficheros.length} ficheros de precios: ${ficheros.join(', ')}`
    : 'Aún no hay precios que copiar.',
)
