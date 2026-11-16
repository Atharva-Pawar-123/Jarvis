/**
 * JARVIS Desktop App — Electron Preload Script
 * ==============================================
 * Exposes a secure bridge between the Electron main process
 * and the React renderer process via contextBridge.
 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('jarvisAPI', {
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  openLink: (url) => ipcRenderer.send('open-external', url),

  // Event listeners from main process
  onMuteToggle: (cb) => ipcRenderer.on('toggle-mute', cb),
  onWindowState: (cb) => ipcRenderer.on('window-state', (_, s) => cb(s)),
  onKillDashboard: (cb) => ipcRenderer.on('kill-dashboard', cb),
})
