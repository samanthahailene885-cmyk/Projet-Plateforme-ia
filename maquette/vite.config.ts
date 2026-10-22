import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function windowlessPython() {
  if (process.platform !== 'win32') return 'python'
  const found = spawnSync('where.exe', ['python'], { encoding: 'utf8' })
  const candidates = (found.stdout || '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  for (const exe of candidates) {
    if (exe.toLowerCase().includes('windowsapps')) continue
    const windowless = exe.replace(/python\.exe$/i, 'pythonw.exe')
    if (windowless !== exe && fs.existsSync(windowless)) return windowless
  }
  return 'python'
}

function djangoIsUp() {
  return new Promise<boolean>((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port: 8000 })
    const giveUp = setTimeout(() => {
      socket.destroy()
      resolve(false)
    }, 400)
    socket.once('connect', () => {
      clearTimeout(giveUp)
      socket.end()
      resolve(true)
    })
    socket.once('error', () => {
      clearTimeout(giveUp)
      resolve(false)
    })
  })
}

let djangoStart: Promise<void> | null = null

function wakeDjango() {
  if (!djangoStart) {
    djangoStart = (async () => {
      if (await djangoIsUp()) return
      // pythonw n'ouvre pas d'invite. --noreload évite le second processus de Django, qui en ouvrait une.
      const child = spawn(windowlessPython(), ['manage.py', 'runserver', '127.0.0.1:8000', '--noreload'], {
        cwd: projectRoot,
        stdio: 'ignore',
        windowsHide: true,
      })
      child.unref()
      for (let attempt = 0; attempt < 40; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 250))
        if (await djangoIsUp()) return
      }
    })().finally(() => {
      djangoStart = null
    })
  }
  return djangoStart
}

function ensureDjango(): Plugin {
  return {
    name: 'ensure-django',
    configureServer(server) {
      const needsData = (url = '') => ['/api', '/login', '/logout', '/dashboard', '/reports', '/decision-ai', '/media'].some((prefix) => url.startsWith(prefix))
      server.middlewares.use((req, _res, next) => {
        if (!needsData(req.url || '')) {
          next()
          return
        }
        wakeDjango().then(() => next()).catch(() => next())
      })
      void wakeDjango()
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
