const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Get backend URL
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),

  // Set backend URL
  setBackendUrl: (url) => ipcRenderer.invoke('set-backend-url', url),

  // Check if backend is reachable
  checkBackendHealth: () => ipcRenderer.invoke('check-backend-health'),

  // Get app version
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),

  // Open external URL in default browser
  openExternal: (url) => {
    const { shell } = require('electron');
    shell.openExternal(url);
  },
});
