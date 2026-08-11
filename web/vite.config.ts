import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  // Ruta relativa para que funcione tanto en local como bajo /usuario/repo/
  base: './',
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icono-192.png', 'icono-512.png'],
      manifest: {
        name: 'Trenes Madrid ⇄ Elche',
        short_name: 'Trenes Elche',
        description: 'Los precios más bajos de tren entre Madrid y Elche.',
        lang: 'es',
        theme_color: '#b3126b',
        background_color: '#f6f7f9',
        display: 'standalone',
        orientation: 'portrait',
        categories: ['travel', 'utilities'],
        // PNG y no solo SVG: sin un 192 y un 512 en PNG, Chrome no llega a
        // ofrecer la instalación (comprobado: no dispara beforeinstallprompt),
        // y Safari no acepta SVG como icono de pantalla de inicio. El SVG se
        // queda para la pestaña, donde sí escala mejor.
        // Se regeneran con: python scripts/generar_iconos.py
        icons: [
          { src: 'icono-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icono-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'icono-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
          { src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico}'],
        // El service worker se regenera en cada compilación, así que la lógica
        // propia -recibir notificaciones- vive aparte y se importa. Ver
        // public/push-sw.js.
        importScripts: ['push-sw.js'],
        // Sin esto, tras un despliegue la app sigue mostrando la versión
        // anterior hasta que se cierran todas sus pestañas. Con la app
        // instalada en el móvil eso puede ser días.
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // Los datos se sirven de red primero, pero quedan cacheados para
            // poder abrir la app sin cobertura y ver la última foto conocida.
            urlPattern: /\/data\/.*\.json$/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'datos-precios',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 14 },
            },
          },
        ],
      },
    }),
  ],
})
