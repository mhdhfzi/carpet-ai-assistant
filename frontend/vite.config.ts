import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  // Library builds don't replace this automatically, and React reads it to pick its
  // development or production build.
  define: { 'process.env.NODE_ENV': JSON.stringify(mode) },
  server: {
    // In development the demo page calls /api on its own origin and Vite forwards it to
    // the FastAPI backend, so the browser never makes a cross-origin request.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    // The widget ships as ONE self-contained script (React and CSS included) that any
    // website can embed with a <script> tag, without a build step on the host site.
    lib: {
      entry: 'src/chat/embed.tsx',
      name: 'CuciChat',
      formats: ['iife'],
      fileName: () => 'widget.js',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
}))
