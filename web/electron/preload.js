const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:is-maximized'),
  onMaximizeChange: (cb) => ipcRenderer.on('window:maximize-change', (_e, s) => cb(s)),

  isElectron: () => ipcRenderer.invoke('is-electron'),
  checkVersion: () => ipcRenderer.invoke('version:check'),
  updateVersion: () => ipcRenderer.invoke('version:update'),
  getVersion: () => ipcRenderer.invoke('version:current'),
});
