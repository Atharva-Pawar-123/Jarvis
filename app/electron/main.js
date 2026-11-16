/**
 * JARVIS Desktop App — Electron Main Process
 * ============================================
 * Creates the frameless native window, spawns the Python backend,
 * manages the system tray, and handles IPC from the React frontend.
 */

const { app, BrowserWindow, Tray, Menu, ipcMain, nativeTheme, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const isDev = false

let mainWindow, tray, pythonProcess

// ── LAUNCH PYTHON BACKEND ──────────────────────────────────────────
function startPythonBackend() {
  const pythonExe = path.join('D:', 'JARVIS', 'venv', 'Scripts', 'python.exe')
  const serverScript = path.join('D:', 'JARVIS', 'server', 'api_server.py')

  pythonProcess = spawn(pythonExe, [serverScript], {
    detached: false,
    stdio: ['ignore', 'pipe', 'pipe'],
    cwd: path.join('D:', 'JARVIS'),
  })

  pythonProcess.stdout.on('data', (d) =>
    console.log('[JARVIS Backend]', d.toString().trim())
  )
  pythonProcess.stderr.on('data', (d) =>
    console.error('[JARVIS Backend]', d.toString().trim())
  )
  pythonProcess.on('close', (code) =>
    console.log('[JARVIS Backend] exited with code:', code)
  )

  // Wait for backend to initialize before loading frontend
  return new Promise((resolve) => setTimeout(resolve, 3000))
}

// ── CREATE MAIN WINDOW ─────────────────────────────────────────────
async function createWindow() {
  await startPythonBackend()

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    transparent: false,
    backgroundColor: '#040912',
    titleBarStyle: 'hidden',
    icon: path.join(__dirname, '../public/icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true,
      devTools: isDev,
    },
  })

  // Load React app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  // Window state management
  mainWindow.on('maximize', () =>
    mainWindow.webContents.send('window-state', 'maximized')
  )
  mainWindow.on('unmaximize', () =>
    mainWindow.webContents.send('window-state', 'normal')
  )
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault()
      mainWindow.hide()
    }
  })
}

// ── SYSTEM TRAY ────────────────────────────────────────────────────
function createTray() {
  tray = new Tray(path.join(__dirname, '../public/icon.png'))
  const menu = Menu.buildFromTemplate([
    { label: 'Open JARVIS', click: () => mainWindow.show() },
    {
      label: 'Mute Mic (F4)',
      click: () => mainWindow.webContents.send('toggle-mute'),
    },
    { type: 'separator' },
    {
      label: 'Kill Dashboard',
      click: () => mainWindow.webContents.send('kill-dashboard'),
    },
    { type: 'separator' },
    {
      label: 'Quit JARVIS',
      click: () => {
        app.isQuitting = true
        app.quit()
      },
    },
  ])
  tray.setToolTip('J.A.R.V.I.S — Online')
  tray.setContextMenu(menu)
  tray.on('click', () => mainWindow.show())
}

// ── IPC HANDLERS (Window controls from custom title bar) ───────────
ipcMain.on('window-minimize', () => mainWindow.minimize())
ipcMain.on('window-maximize', () => {
  mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize()
})
ipcMain.on('window-close', () => mainWindow.hide())
ipcMain.on('open-external', (_, url) => shell.openExternal(url))

// ── APP LIFECYCLE ──────────────────────────────────────────────────
app.whenReady().then(() => {
  nativeTheme.themeSource = 'dark'
  createWindow()
  createTray()
})

app.on('window-all-closed', (e) => e.preventDefault()) // keep alive in tray

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill()
    console.log('[JARVIS] Python backend terminated.')
  }
})

app.on('activate', () => {
  if (mainWindow) mainWindow.show()
})
