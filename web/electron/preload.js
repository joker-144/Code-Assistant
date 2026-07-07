const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: () => ipcRenderer.invoke('is-electron'),
  checkVersion: () => ipcRenderer.invoke('version:check'),
  updateVersion: () => ipcRenderer.invoke('version:update'),
  getVersion: () => ipcRenderer.invoke('version:current'),
});
