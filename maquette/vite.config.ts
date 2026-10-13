import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { spawn } from 'node:child_process'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function ensureDjango(): Plugin {
  return {
    name: 'ensure-django',
    configureServer() {
      const socket = net.connect({ host: '127.0.0.1', port: 8000 })
      const giveUp = setTimeout(() => socket.destroy(), 800)
      socket.once('connect', () => {
        clearTimeout(giveUp)
        socket.end()
      })
      socket.once('error', () => {
        clearTimeout(giveUp)
        const child = spawn('python', ['manage.py', 'runserver', '127.0.0.1:8000'], {
          cwd: projectRoot,
          stdio: 'ignore',
          detached: true,
          windowsHide: true,
        })
        child.unref()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), ensureDjango()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/dashboard': 'http://127.0.0.1:8000',
      '/reports': 'http://127.0.0.1:8000',
      '/decision-ai': 'http://127.0.0.1:8000',
      '/login': 'http://127.0.0.1:8000',
      '/logout': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
    },
  },
})
