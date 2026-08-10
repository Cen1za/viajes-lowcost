/**
 * Instalación de la app en el móvil.
 *
 * Chrome y Edge disparan `beforeinstallprompt` cuando la página cumple los
 * requisitos de PWA; guardamos ese evento para poder lanzar el diálogo nativo
 * desde un botón nuestro. Safari no implementa nada de esto, así que ahí solo
 * queda explicar el camino manual.
 */

import { useEffect, useState } from 'react'

interface EventoInstalacion extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export type EstadoInstalacion =
  | 'instalada'      // ya se está usando como app
  | 'disponible'     // podemos lanzar el diálogo nativo
  | 'manual'         // hay que explicar cómo hacerlo a mano (iOS, Firefox…)

export function useInstalacion() {
  const [evento, setEvento] = useState<EventoInstalacion | null>(null)
  const [instalada, setInstalada] = useState(
    () =>
      window.matchMedia('(display-mode: standalone)').matches ||
      // Safari en iOS expone esto en vez del display-mode.
      (navigator as { standalone?: boolean }).standalone === true,
  )

  useEffect(() => {
    const alPreguntar = (e: Event) => {
      e.preventDefault() // así el navegador no muestra su propia barra
      setEvento(e as EventoInstalacion)
    }
    const alInstalar = () => {
      setInstalada(true)
      setEvento(null)
    }

    window.addEventListener('beforeinstallprompt', alPreguntar)
    window.addEventListener('appinstalled', alInstalar)
    return () => {
      window.removeEventListener('beforeinstallprompt', alPreguntar)
      window.removeEventListener('appinstalled', alInstalar)
    }
  }, [])

  const estado: EstadoInstalacion = instalada
    ? 'instalada'
    : evento
      ? 'disponible'
      : 'manual'

  async function instalar() {
    if (!evento) return
    await evento.prompt()
    const { outcome } = await evento.userChoice
    if (outcome === 'accepted') setInstalada(true)
    setEvento(null) // el evento solo se puede usar una vez
  }

  return { estado, instalar, esApple: /iPad|iPhone|iPod/.test(navigator.userAgent) }
}
