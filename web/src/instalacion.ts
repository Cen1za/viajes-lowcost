/**
 * Instalación de la app en el móvil.
 *
 * Chrome y Edge disparan `beforeinstallprompt` cuando la página cumple los
 * requisitos de PWA; guardamos ese evento para poder lanzar el diálogo nativo
 * desde un botón nuestro. Safari no implementa nada de esto, así que ahí solo
 * queda explicar el camino manual.
 *
 * El evento se escucha desde el módulo y no desde el hook por dos motivos:
 * llega **una sola vez**, así que si cada componente montara su propio oyente
 * solo se enteraría el primero —el botón de la cabecera se ponía y la tarjeta
 * de Ajustes seguía diciendo que había que instalarla a mano—, y además puede
 * llegar antes de que React monte nada.
 */

import { useSyncExternalStore } from 'react'

interface EventoInstalacion extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export type EstadoInstalacion =
  | 'instalada'      // ya se está usando como app
  | 'disponible'     // podemos lanzar el diálogo nativo
  | 'manual'         // hay que explicar cómo hacerlo a mano (iOS, Firefox…)

let evento: EventoInstalacion | null = null
let instalada = false
const oyentes = new Set<() => void>()

function avisar() {
  for (const oyente of oyentes) oyente()
}

function suscribir(oyente: () => void) {
  oyentes.add(oyente)
  return () => {
    oyentes.delete(oyente)
  }
}

function enStandalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    // Safari en iOS expone esto en vez del display-mode.
    (navigator as { standalone?: boolean }).standalone === true
  )
}

if (typeof window !== 'undefined') {
  instalada = enStandalone()

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault() // así el navegador no muestra su propia barra
    evento = e as EventoInstalacion
    avisar()
  })

  window.addEventListener('appinstalled', () => {
    instalada = true
    evento = null
    avisar()
  })
}

function estadoActual(): EstadoInstalacion {
  if (instalada) return 'instalada'
  return evento ? 'disponible' : 'manual'
}

export function useInstalacion() {
  const estado = useSyncExternalStore(
    suscribir,
    estadoActual,
    () => 'manual' as EstadoInstalacion,
  )

  async function instalar() {
    if (!evento) return
    await evento.prompt()
    const { outcome } = await evento.userChoice
    if (outcome === 'accepted') instalada = true
    evento = null // el evento solo se puede usar una vez
    avisar()
  }

  return { estado, instalar, esApple: /iPad|iPhone|iPod/.test(navigator.userAgent) }
}
