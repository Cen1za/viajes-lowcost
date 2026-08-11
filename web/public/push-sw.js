/**
 * Notificaciones del móvil.
 *
 * Este fichero lo carga el service worker que genera vite-plugin-pwa (con
 * `workbox.importScripts`), porque ese se regenera en cada compilación y no se
 * puede editar a mano.
 *
 * El mensaje lo manda GitHub Actions; ver buscador/avisos/webpush.py.
 */

self.addEventListener('push', (evento) => {
  // Si el aviso llega sin datos o con basura, se muestra algo genérico en vez
  // de no mostrar nada: una notificación vacía asusta más que informa.
  let datos = { titulo: 'Trenes Madrid ⇄ Elche', cuerpo: 'Hay novedades de precios.', url: '/' }
  try {
    if (evento.data) datos = { ...datos, ...evento.data.json() }
  } catch (e) {
    if (evento.data) datos.cuerpo = evento.data.text()
  }

  evento.waitUntil(
    self.registration.showNotification(datos.titulo, {
      body: datos.cuerpo,
      icon: './favicon.svg',
      badge: './favicon.svg',
      lang: 'es',
      // Que un aviso nuevo sustituya al anterior en vez de apilarse: son
      // precios, y el último es el que vale.
      tag: 'precios-tren',
      renotify: true,
      data: { url: datos.url || './' },
    }),
  )
})

self.addEventListener('notificationclick', (evento) => {
  evento.notification.close()
  const destino = (evento.notification.data && evento.notification.data.url) || './'

  evento.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((abiertas) => {
      // Si la app ya está abierta se trae al frente en vez de abrir otra copia.
      for (const cliente of abiertas) {
        if ('focus' in cliente) return cliente.focus()
      }
      return self.clients.openWindow(destino)
    }),
  )
})
