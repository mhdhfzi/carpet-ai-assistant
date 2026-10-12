import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Two builds (see "build" in package.json):
//   vite build               -> the demo page (index.html) and the owner dashboard (admin.html)
//   vite build --mode widget -> dist/widget.js, the embeddable chat widget
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  server: {
    // In development the pages call /api on their own origin and Vite forwards it to the
    // FastAPI backend, so the browser never makes a cross-origin request.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  ...(mode === 'widget' ? widgetBuild : appBuild),
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
}))

const appBuild = {
  build: {
    rollupOptions: { input: { demo: 'index.html', admin: 'admin.html' } },
  },
}

const widgetBuild = {
  // Library builds don't set this, and React reads it to choose its production build.
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    // ONE self-contained script (React and CSS included) that any website can embed with a
    // <script> tag, without a build step on the host site.
    lib: {
      entry: 'src/chat/embed.tsx',
      name: 'KilauChat',
      formats: ['iife' as const],
      fileName: () => 'widget.js',
    },
    emptyOutDir: false, // keep the app build in dist/
  },
}
